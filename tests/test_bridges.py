import asyncio
import io
import json
import tempfile
import unittest
import wave
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch
from types import SimpleNamespace
from aiohttp.test_utils import TestClient, TestServer
from wyoming.event import Event, async_read_event, async_write_event
from wyoming.info import Info
from bridges import VoiceHandler, service_info, ollama_app, VOICE
from config import Settings, LEBANESE_PROMPT
from services import Services, to_provider_messages, from_provider_message, compact_tools, prune_completed_tool_history
from server import desk_app

def wav_bytes():
    output = io.BytesIO()
    with wave.open(output, 'wb') as wav:
        wav.setnchannels(1); wav.setsampwidth(2); wav.setframerate(24000)
        wav.writeframes(b'\0\0' * 2400)
    return output.getvalue()

class ConversionTests(unittest.TestCase):
    def test_history_keeps_current_action_and_completed_dialogue_without_old_tool_results(self):
        old_user = {'role':'user','content':'Turn on the lights'}
        old_call = {'role':'assistant','tool_calls':[{'function':{'name':'HassTurnOn','arguments':{}}}]}
        old_result = {'role':'tool','content':'large old device snapshot'}
        old_answer = {'role':'assistant','content':'Done'}
        new_user = {'role':'user','content':'What is the temperature?'}
        new_call = {'role':'assistant','tool_calls':[{'function':{'name':'GetLiveContext','arguments':{}}}]}
        new_result = {'role':'tool','content':'current device state'}
        messages = [{'role':'system','content':'instructions'},old_user,old_call,old_result,old_answer,new_user,new_call,new_result]
        self.assertEqual(prune_completed_tool_history(messages),[messages[0],old_user,old_answer,new_user,new_call,new_result])
        unfinished = messages[:4] + [new_user,new_call,new_result]
        self.assertEqual(prune_completed_tool_history(unfinished),[messages[0],new_user,new_call,new_result])
        self.assertEqual(len(messages),8)

    def test_tool_compaction_preserves_validation_and_unit_guidance(self):
        parameters = {'type':'object','additionalProperties':False,'required':['brightness','title'],
            'properties':{'brightness':{'type':'integer','minimum':0,'maximum':100,'description':'Brightness as a percent from 0 to 100'},
                          'name':{'type':'string','description':'The name of the device','enum':['Lamp 4']},
                          'title':{'type':'string','description':'A user-defined title'},
                          'settings':{'enum':[{'title':'Keep literal enum data','description':'Also literal'}]}},
            'description':'Parameters for an action'}
        tools = [{'type':'function','function':{'name':'HassLightSet','description':'Set the brightness of a light.','parameters':parameters}}]
        compact = compact_tools(tools)
        schema = compact[0]['function']['parameters']
        self.assertEqual(schema['required'],['brightness','title'])
        self.assertFalse(schema['additionalProperties'])
        self.assertEqual(schema['properties']['brightness'],parameters['properties']['brightness'])
        self.assertEqual(schema['properties']['name']['enum'],['Lamp 4'])
        self.assertIn('title',schema['properties'])
        self.assertEqual(schema['properties']['settings'],parameters['properties']['settings'])
        self.assertEqual(compact[0]['function']['description'],tools[0]['function']['description'])
        self.assertIn('description',parameters)  # Original schemas are not mutated.

    def test_tool_round_trip_without_provider_specific_ids(self):
        messages = [
            {'role': 'user', 'content': 'طفي ضو الصالون'},
            {'role': 'assistant', 'content': '', 'tool_calls': [
                {'function': {'name': 'HassTurnOff', 'arguments': {'name': 'صالون'}}}]},
            {'role': 'tool', 'content': '{"success":true}'},
        ]
        converted = to_provider_messages(messages)
        self.assertEqual(converted[0]['content'], LEBANESE_PROMPT)
        self.assertEqual(converted[2]['tool_calls'][0]['id'], converted[3]['tool_call_id'])
        self.assertEqual(json.loads(converted[2]['tool_calls'][0]['function']['arguments']), {'name': 'صالون'})
        returned = from_provider_message({'role': 'assistant', 'tool_calls': [{'function': {
            'name': 'HassTurnOff', 'arguments': '{"name":"صالون"}'}}]})
        self.assertEqual(returned['tool_calls'][0]['function']['arguments']['name'], 'صالون')

    def test_wyoming_info_parses_with_official_library(self):
        info = Info.from_event(Event(type='info', data=service_info()))
        self.assertEqual(info.tts[0].voices[0].languages, ['ar'])
        self.assertTrue(info.asr[0].requires_external_vad)

    def test_secrets_not_in_public_settings(self):
        with tempfile.TemporaryDirectory() as directory:
            settings = Settings(Path(directory) / 'settings.json')
            settings.update({'groq_key': 'test-secret'})
            public = json.dumps(settings.public())
            self.assertNotIn('test-secret', public)
            self.assertNotIn(settings.data['bridge_token'], public)
            settings.update({'groq_key': ''})
            self.assertEqual(settings.data['groq_key'], 'test-secret')

class ProviderRetryTests(unittest.IsolatedAsyncioTestCase):
    def response(self, status, payload, headers=None):
        response = MagicMock(status=status, headers=headers or {})
        response.json = AsyncMock(return_value=payload)
        context = MagicMock()
        context.__aenter__ = AsyncMock(return_value=response)
        context.__aexit__ = AsyncMock(return_value=False)
        return context

    async def test_rate_limit_retries_same_inference_once_after_reported_wait(self):
        session = MagicMock()
        session.request.side_effect = [
            self.response(429,{'error':{'message':'Try again in 3.5s.'}}),
            self.response(200,{'choices':[]}),
        ]
        services = Services(SimpleNamespace(data={'groq_key':'test-secret'}),session)
        body = {'model':'test-model','messages':[{'role':'tool','content':'confirmed result'}]}
        with patch('services.asyncio.sleep',new_callable=AsyncMock) as sleep:
            result = await services.groq('/chat/completions',body=body)
        self.assertEqual(result,{'choices':[]})
        sleep.assert_awaited_once_with(3.75)
        self.assertEqual(session.request.call_count,2)
        self.assertEqual(session.request.call_args_list[0],session.request.call_args_list[1])

    async def test_audio_is_not_replayed_and_long_or_repeated_limits_stop(self):
        for route, retry_after, expected_calls in [
            ('/audio/transcriptions','2',1),('/chat/completions','61',1),('/chat/completions','1',2)]:
            session = MagicMock()
            session.request.side_effect = [self.response(429,{'error':{'message':'Rate limit'}},{'Retry-After':retry_after}) for _ in range(2)]
            services = Services(SimpleNamespace(data={'groq_key':'test-secret'}),session)
            with patch('services.asyncio.sleep',new_callable=AsyncMock):
                with self.assertRaisesRegex(ValueError,'Groq \\(429\\)'):
                    await services.groq(route,body={'test':True})
            self.assertEqual(session.request.call_count,expected_calls)

    async def test_observed_forty_nine_second_rate_wait_is_supported(self):
        session = MagicMock()
        session.request.side_effect = [self.response(429,{'error':{'message':'Try again in 49.002857142s.'}}), self.response(200,{'ok':True})]
        services = Services(SimpleNamespace(data={'groq_key':'test-secret'}),session)
        with patch('services.asyncio.sleep',new_callable=AsyncMock) as sleep:
            self.assertEqual(await services.groq('/chat/completions',body={}),{'ok':True})
        sleep.assert_awaited_once_with(49.252857142)

    async def test_concurrent_inference_requests_do_not_compete_during_a_wait(self):
        entered = asyncio.Event()
        release = asyncio.Event()
        first = self.response(200,{'one':True})
        async def first_json(**kwargs):
            entered.set()
            await release.wait()
            return {'one':True}
        first.__aenter__.return_value.json.side_effect = first_json
        session = MagicMock()
        session.request.side_effect = [first,self.response(200,{'two':True})]
        services = Services(SimpleNamespace(data={'groq_key':'test-secret'}),session)
        first_task = asyncio.create_task(services.groq('/chat/completions',body={'one':True}))
        await entered.wait()
        second_task = asyncio.create_task(services.groq('/chat/completions',body={'two':True}))
        await asyncio.sleep(0)
        self.assertEqual(session.request.call_count,1)
        release.set()
        self.assertEqual(await asyncio.gather(first_task,second_task),[{'one':True},{'two':True}])

class BridgeTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.services = AsyncMock()
        self.services.synthesize.return_value = wav_bytes()
        self.services.transcribe.return_value = 'مرحبا'
        self.services.chat.return_value = {'role': 'assistant', 'content': 'أهلين!'}
        self.client = TestClient(TestServer(ollama_app(self.services, 'test-token')))
        await self.client.start_server()

    async def asyncTearDown(self):
        await self.client.close()

    async def test_ollama_discovery_auth_and_streaming(self):
        response = await self.client.get('/api/tags')
        self.assertEqual(response.status, 401)
        auth = {'Authorization': 'Bearer test-token'}
        response = await self.client.get('/api/tags', headers=auth)
        self.assertEqual((await response.json())['models'][0]['name'], VOICE)
        response = await self.client.post('/api/show', headers=auth, json={'model':VOICE})
        self.assertIn('tools', (await response.json())['capabilities'])
        tools = [{'type':'function','function':{'name':'HassTurnOff','parameters':{'type':'object'}}}]
        response = await self.client.post('/api/chat', headers=auth,
            json={'model':VOICE,'stream':True,'messages':[{'role':'user','content':'مرحبا'}], 'tools':tools})
        self.assertEqual(response.content_type,'application/x-ndjson')
        payload = json.loads(await response.text())
        self.assertEqual(payload['message']['content'],'أهلين!')
        self.assertTrue(payload['done'])
        self.services.chat.assert_awaited_once_with([{'role':'user','content':'مرحبا'}], tools)

    async def test_wyoming_real_tcp_audio_round_trip(self):
        tasks = set()
        async def accept(reader, writer):
            task = asyncio.current_task(); tasks.add(task)
            try:
                await VoiceHandler(reader,writer,self.services).run()
            finally:
                tasks.discard(task)
        server = await asyncio.start_server(accept,'127.0.0.1',0)
        reader, writer = await asyncio.open_connection('127.0.0.1',server.sockets[0].getsockname()[1])
        try:
            await async_write_event(Event(type='describe'),writer)
            info = await asyncio.wait_for(async_read_event(reader),2)
            self.assertTrue(Info.from_event(info).tts)
            await async_write_event(Event(type='synthesize',data={'text':'مرحبا'}),writer)
            start = await asyncio.wait_for(async_read_event(reader),2)
            self.assertEqual(start.type,'audio-start')
            audio = bytearray()
            while True:
                event = await asyncio.wait_for(async_read_event(reader),2)
                if event.type == 'audio-stop': break
                self.assertEqual(event.type,'audio-chunk'); audio.extend(event.payload)
            self.assertEqual(len(audio),4800)
            fmt = {'rate':16000,'width':2,'channels':1}
            for event in [Event(type='transcribe'), Event(type='audio-start',data=fmt),
                          Event(type='audio-chunk',data=fmt,payload=b'\0\0'*1600), Event(type='audio-stop')]:
                await async_write_event(event,writer)
            transcript = await asyncio.wait_for(async_read_event(reader),2)
            self.assertEqual(transcript.data['text'],'مرحبا')
            uploaded = self.services.transcribe.call_args.args[0]
            with wave.open(io.BytesIO(uploaded),'rb') as wav:
                self.assertEqual(wav.getframerate(),16000)
                self.assertEqual(wav.getnframes(),1600)
        finally:
            writer.close(); await writer.wait_closed()
            server.close(); await server.wait_closed()
            if tasks: await asyncio.wait_for(asyncio.gather(*list(tasks)),2)

    async def test_failed_speech_closes_connection_instead_of_hanging(self):
        self.services.synthesize.side_effect = ValueError('Voice quota exhausted')
        tasks = set()
        async def accept(reader,writer):
            task = asyncio.current_task(); tasks.add(task)
            try:
                await VoiceHandler(reader,writer,self.services).run()
            finally:
                tasks.discard(task)
        server = await asyncio.start_server(accept,'127.0.0.1',0)
        reader,writer = await asyncio.open_connection('127.0.0.1',server.sockets[0].getsockname()[1])
        try:
            await async_write_event(Event(type='synthesize',data={'text':'مرحبا'}),writer)
            error = await asyncio.wait_for(async_read_event(reader),2)
            self.assertEqual(error.type,'error')
            self.assertIn('quota',error.data['text'])
            self.assertIsNone(await asyncio.wait_for(async_read_event(reader),2))
        finally:
            writer.close(); await writer.wait_closed()
            server.close(); await server.wait_closed()
            if tasks: await asyncio.wait_for(asyncio.gather(*list(tasks)),2)

    async def test_desk_rejects_cross_origin_settings_changes(self):
        with tempfile.TemporaryDirectory() as directory:
            settings = Settings(Path(directory)/'settings.json')
            client = TestClient(TestServer(desk_app(settings,self.services)))
            await client.start_server()
            try:
                response = await client.post('/api/settings',headers={'Origin':'https://unrelated.example'},json={'groq_key':'bad'})
                self.assertEqual(response.status,403)
                self.assertEqual(settings.data['groq_key'],'')
                response = await client.get('/api/status')
                self.assertEqual(response.status,200)
                self.assertNotIn('bridge_token',await response.json())
            finally:
                await client.close()

if __name__ == '__main__':
    unittest.main()

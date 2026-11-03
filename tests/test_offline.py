import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch
from offline_services import OfflineServices


class OfflineBoundaryTests(unittest.IsolatedAsyncioTestCase):
    async def test_provider_routes_fail_without_network_even_if_keys_exist(self):
        session = SimpleNamespace(request=AsyncMock())
        service = OfflineServices(SimpleNamespace(data={'groq_key': 'unused'}), session)
        for route in ('/models', '/audio/transcriptions', '/unknown'):
            with self.assertRaisesRegex(ValueError, 'disabled'):
                await service.groq(route)
        session.request.assert_not_called()

    async def test_chat_uses_local_inference_without_provider_fallback(self):
        session = SimpleNamespace(request=AsyncMock())
        service = OfflineServices(SimpleNamespace(data={}), session)
        expected = {'role': 'assistant', 'content': 'تمام'}
        with patch.object(service, '_chat', return_value=expected) as infer:
            response = await service.groq('/chat/completions', body={'messages': []})
        self.assertEqual(response['choices'][0]['message'], expected)
        infer.assert_called_once()
        session.request.assert_not_called()

    async def test_local_model_failure_is_not_sent_to_cloud(self):
        session = SimpleNamespace(request=AsyncMock())
        service = OfflineServices(SimpleNamespace(data={}), session)
        with patch.object(service, '_chat', side_effect=RuntimeError('missing local model')):
            with self.assertRaisesRegex(RuntimeError, 'missing local model'):
                await service.groq('/chat/completions', body={})
        session.request.assert_not_called()

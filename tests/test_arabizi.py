import unittest
from studio.arabizi import convert, spell


class ArabiziTests(unittest.TestCase):
    def test_everyday_sentence(self):
        result = convert('maraheb shou el wade3 mesheh el hal kello tamem ?')
        self.assertEqual(result['arabic'], 'مرحبا شو الوضع ماشي الحال كلّو تمام ؟')
        self.assertTrue(result['confident'])
        self.assertEqual(result['unknown'], [])

    def test_home_command_with_prefixes(self):
        result = convert('taffe el daw bel salon w sha8el lmkayyef')
        self.assertEqual(result['arabic'], 'طفّي الضوّ بالصالون وشغّل المكيّف')
        self.assertTrue(result['confident'])

    def test_digits_become_letters(self):
        self.assertEqual(spell('3ande'), 'عندة')
        self.assertEqual(spell('7abeeb'), 'حبيب')
        self.assertEqual(spell('7abib'), 'حبب')  # a single mid-word vowel is short: not written
        self.assertEqual(spell('kello'), 'كلّو')
        self.assertEqual(spell('2alb'), 'ألب')

    def test_two_is_always_hamza_never_qaf(self):
        self.assertEqual(spell('la2'), 'لأ')
        self.assertEqual(spell('so2al'), 'سؤل')
        self.assertEqual(spell('fee2'), 'فيئ')
        self.assertEqual(spell('2enta')[0], 'إ')
        self.assertEqual(spell('2aal'), 'آل')
        self.assertEqual(convert('halla2 2addesh el sa3a?')['arabic'], 'هلّأ أدّيش الساعة؟')
        self.assertNotIn('ق', convert('2ahwe 2abel el ghada bt2oul?')['arabic'])
        self.assertEqual(convert('taqs')['arabic'], 'طقس')  # a written q is still ق
        from studio.arabizi import WORDS
        self.assertEqual({k: v for k, v in WORDS.items() if '2' in k and 'ق' in v}, {})

    def test_taught_words_win_and_take_prefixes(self):
        taught = {'blabla': 'بلابلا', 'tamem': 'تمااام'}
        result = convert('el blabla tamem', taught)
        self.assertEqual(result['arabic'], 'البلابلا تمااام')
        self.assertEqual(result['unknown'], [])
        self.assertEqual(convert('elblabla', taught)['arabic'], 'البلابلا')
        self.assertEqual(convert('tamem')['arabic'], 'تمام')  # the built-in list is untouched

    def test_small_words_are_not_shadowed(self):
        self.assertEqual(convert('al beit')['arabic'], 'البيت')
        self.assertEqual(convert('la, mish hon')['arabic'], 'لا، مش هون')
        self.assertEqual(convert('kol shi')['arabic'], 'كل شي')

    def test_standalone_numbers_and_arabic_are_kept(self):
        result = convert('badde 3 kilo خبز bokra')
        self.assertEqual(result['arabic'], 'بدّي 3 كلّو خبز بكرا')

    def test_unknown_words_are_spelled_and_reported(self):
        result = convert('shou hayda el blabla?')
        self.assertEqual(result['arabic'], 'شو هيدا البلبلا؟')
        self.assertEqual(result['unknown'], ['blabla'])

    def test_english_is_not_mistaken_for_arabizi(self):
        result = convert('please read the whole document before replying')
        self.assertFalse(result['confident'])
        self.assertEqual(convert('')['latin_words'], 0)
        self.assertFalse(convert('شو الوضع؟')['confident'])

    def test_suffixes_and_hyphens(self):
        self.assertEqual(convert('beitak')['arabic'], 'بيتك')
        self.assertEqual(convert('el-salon')['arabic'], 'الصالون')
        self.assertEqual(convert('ma3kon')['arabic'], 'معكن')

    def test_punctuation_becomes_arabic_when_confident(self):
        self.assertEqual(convert('kifak, mnih?')['arabic'], 'كيفك، منيح؟')
        self.assertEqual(convert('1, 2, 3?')['arabic'], '1, 2, 3?')


if __name__ == '__main__':
    unittest.main()

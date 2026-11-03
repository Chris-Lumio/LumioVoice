"""Lebanese Arabizi (Latin letters and digits) to Arabic script.

Common words come from a dictionary; anything else is transliterated letter by
letter. Spelling varies a lot between people, so the dictionary carries the
usual alternatives and callers show the result for correction.

The digit 2 is always the hamza (ء), as Lebanese speakers pronounce it, never ق;
only a written q becomes ق.
"""
import re

SHADDA = 'ّ'


def _expand(table):
    words = {}
    for keys, arabic in table.items():
        for key in keys.split('|'):
            words[key] = arabic
    return words


WORDS = _expand({
    # Greetings and politeness
    'maraheb|mar7aba|marhaba|mar7abe|marhabe': 'مرحبا',
    'ahla|ahlan': 'أهلا', 'ahlen|ahleen|ahlein|ahlayn': 'أهلين', 'hala': 'هلا',
    'kifak|keefak|kefak': 'كيفك', 'kifik|keefik|kefik': 'كيفِك', 'kifkon|keefkon': 'كيفكن',
    'kifo|keefo': 'كيفو', 'kifa|keefa': 'كيفا', 'kif|keef|kef': 'كيف',
    'shukran|shokran|chukran|shoukran': 'شكراً', 'merci|mersi': 'ميرسي', '3afwan': 'عفواً',
    'ma3lesh|ma3lech|ma3lish': 'معلش', 'sorry': 'سوري', 'please': 'بليز',
    'hi|hey': 'هاي', 'hello': 'هالو', 'bye': 'باي', 'ok|okay|okey': 'أوكي',
    'bonjour|bonjur': 'بونجور', 'bonjourein|bonjourain': 'بونجورين', 'bonsoir': 'بونسوار',
    'yislamo|yeslamo|yslamo|yislamou': 'يسلمو', 'yislamak|ysalmak|yeslamak': 'يسلمك',
    'ya3tik|ya3teek|y3tik': 'يعطيك', '3afye|3afyi|3afieh|3afieh': 'عافية',
    '7amdella|hamdella|7amdellah|hamdellah|7amdela': 'الحمدلله', 'allah|alla': 'الله',
    'inshallah|inshalla|nshalla|nshallah|inchallah': 'إن شاء الله', 'wallah|walla|wlh': 'والله',
    'yarab|ya rab': 'يا رب', 'rab': 'رب', 'tfadal|tfaddal|tfadal': 'تفضّل', 'tfadale|tfaddali': 'تفضّلي',
    'mabrouk|mabrook|mabruk': 'مبروك', 'sa7tein|sahtein|sa7tayn': 'صحتين', 'na3iman|n3iman': 'نعيماً',
    'salam|salem': 'سلام', 'bkhatrak|bkhatrik|b5atrak': 'بخاطرك', 'allah ma3ak': 'الله معك',
    # Question words and small words
    'shou|shu|chou|chu|sho|shoo': 'شو', 'lesh|leish|laysh|lech|leysh': 'ليش',
    'wen|wein|ween|wayn|weyn': 'وين', 'emta|aymta|emtan|aimta': 'إيمتى',
    'adde|addeh|2adde|2addeh|2addesh|adesh|addesh|2adesh|2adeish': 'أدّيش',
    'meen|mean|miin|mein': 'مين', 'kam|kem': 'كم', 'ayya|aya|ayye': 'أيّا', 'ay': 'أي',
    'kif ma': 'كيف ما', 'hal': 'حال', '7al': 'حال',
    'el|al|il|l|elle': 'ال', 'w|we|ou|wa': 'و', 'aw|au': 'أو', 'ya': 'يا',
    'bas|bass|bes': 'بس', 'la': 'لا', 'la2|laa|la2a': 'لأ', 'eh|ee|eeh|eih|ei': 'إيه', 'aywa|aywah': 'أيوا',
    'na3am|na3m': 'نعم', 'ah|aah|aa': 'آه', 'mm|hmm': 'همم',
    'ma': 'ما', 'mish|mesh|msh|mich|mech': 'مش', 'mou|mo|mu': 'مو', 'bala|bla': 'بلا',
    'fi|fih|fe|fee': 'في', 'fik|feek|fiik': 'فيك', 'fiki|feeki': 'فيكي', 'fini|feeni|fiini': 'فيني',
    'fio|fiyo|feeyo': 'فيو', 'fiha|feeha|fiya': 'فيا', 'fina|feena': 'فينا', 'fikon|feekon': 'فيكن', 'fihon|feehon': 'فين',
    'mafi|mafee': 'ما في', 'walaw': 'ولو', 'ya3ne|ya3ni|y3ne|y3ni|ya3nii': 'يعني',
    'iza|eza|izza|ezza': 'إذا', 'lamma|lama|lamman': 'لمّا', 'la2an|la2ano|la2eno|la2anno|la2enno': 'لأنّو',
    'ba3d|ba3ad': 'بعد', 'ba3den|ba3dein|ba3deen|ba3dayn': 'بعدين', '2abel|abel|2abl|abl|2abil': 'أبل',
    'ma3': 'مع', 'ma3ak|ma3ek': 'معك', 'ma3e|ma3i|ma3ii': 'معي', 'ma3o': 'معو', 'ma3a': 'معا', 'ma3na': 'معنا',
    '3an': 'عن', '3ala|3la': 'على', '3a': 'عَ', '3al': 'عال', 'men|mn': 'من', 'mnen|mnein|mneen': 'منين',
    'bel|bil|bl': 'بال', 'bi|b': 'بـ', 'lal': 'لل', 'lahon|lahun|la hon': 'لهون',
    '3end|3nd|3and|3ind': 'عند', '3ande|3andi|3ndi|3ende|3endi|3andii': 'عندي', '3andak|3endak|3ndak': 'عندك',
    '3andik|3endik|3ndik': 'عندك', '3ando|3endo|3ndo': 'عندو', '3anda|3enda': 'عندا', '3andna|3endna|3enna': 'عنّا',
    '3andkon|3endkon': 'عندكن', '3andon|3endon': 'عندن',
    'hon|hone|hoon|hown': 'هون', 'honik|honeek|hunik|honeik|hunayk': 'هونيك', 'hek|heik|hayk|haik|heyk': 'هيك',
    'heda|hayda|haida|hayde|haydi|haidi|hay': 'هيدا', 'haydi|haidi|hayde': 'هيدي', 'hol|hawl|hawde|hawdi|hodi|hawdeh': 'هودي',
    'kel|kil|kol|kul|kell|koll': 'كل', 'kello|kelo|kilo|kollo|kulo|kilou|kellou': 'كلّو',
    'kella|kila|kolla': 'كلّا', 'kellon|kelon|kollon|kelloun': 'كلّن', 'kelna|kilna|kollna': 'كلّنا',
    'shi|she|chi|shee|shii': 'شي', 'shaghle|shaghli|sha8le|sha8li|shaghleh|cheghle': 'شغلة',
    'kelme|kilme|kelmi|kilmeh': 'كلمة', '2esa|2essa|essa|2issa': 'أصّة',
    'ktir|kteer|ktyr|kter|kteir|ktiir': 'كتير', 'shway|shwai|shwaye|shwayye|chway|shwayeh|shwayet': 'شوي',
    'akid|akeed|akiid|akeid': 'أكيد', 'tab3an|tab3n': 'طبعاً', 'yalla|yala|yallah|yalah': 'يلا',
    'halla2|hala2|halla|hal2|halla2a|hal2a': 'هلّأ', 'hallaq': 'هلّق', 'lahalla2|la halla2|lahal2': 'لهلّأ',
    'dayman|daymen|daiman|dayme': 'دايماً', 'abadan|abadn': 'أبداً', 'marra|marrah': 'مرّة', 'marrat': 'مرّات',
    'mazbout|mazbot|mazboot|mazbut': 'مظبوط', 'sa7|sa77|sahh|sah': 'صح', 'ghalat|8alat|ghalt': 'غلط',
    'tayyeb|tayeb|tayib|tayyib': 'طيّب', 'tab|tayb': 'طب', '3anjad|3njad|3an jad|3anjd': 'عنجد',
    'mumken|momken|mimken|mumkin|momkin': 'ممكن', 'lezim|lazem|lezem|lazim|laazem': 'لازم',
    'dghre|dighri|deghre|doghri|dighre': 'دغري', 'yimkin|yemken|yemkin|yimken': 'يمكن',
    'khalas|5alas|khalass|5las': 'خلص', 'bejannen|bijannen|bjanen|bijanen|byjannen': 'بيجنّن',
    'tamem|tamam|tmam|tamaam|tmem': 'تمام', 'mnih|mni7|mnee7|mnii7|mneeh|mniih|mne7': 'منيح',
    'mniha|mni7a|mnee7a|mni7ah': 'منيحة', 'mnah|mna7|mnaah': 'مناح',
    # Pronouns
    'ana|ane|anaa': 'أنا', 'enta|inta|ente|inte|ent|int|enteh': 'إنت', 'enti|inti|entii': 'إنتِ',
    'huwe|howe|hiwe|huwwe|houwe': 'هوّي', 'hiye|hiyye|hiyeh|hiya': 'هيّي', 'nahna|ne7na|nihna|nehna|na7na': 'نحنا',
    'ento|entou|intu|intou|entu': 'إنتو', 'henne|hinne|hinni|henni|hennen': 'هنّي',
    'ele|eli|ile|ili': 'إلي', 'elak|ilak|elek': 'إلك', 'elik|ilik': 'إلِك', 'elo|ilo': 'إلو', 'ela|ila': 'إلا',
    'elna|ilna': 'إلنا', 'elkon|ilkon': 'إلكن', 'elon|ilon': 'إلن',
    'lli|elli|yalli|yali|li': 'اللي',
    # Wanting, having, knowing
    'bade|badde|baddi|badi|bedde|beddi|bidi|biddi': 'بدّي', 'badak|baddak|bedak|beddak': 'بدّك',
    'badik|baddik|bedik|beddik': 'بدِّك', 'bado|baddo|bedo|beddo': 'بدّو', 'bada|badda|bedda': 'بدّا',
    'badna|baddna|bedna|beddna': 'بدّنا', 'badkon|baddkon|bedkon': 'بدّكن', 'badon|baddon|bedon': 'بدّن',
    'ba3ref|b3ref|ba3rif|ba3rf|b3rif': 'بعرف', 'bta3ref|bta3rif|bt3ref|bta3rf': 'بتعرف', 'bya3ref|by3ref|bi3ref': 'بيعرف',
    'mna3ref|mn3ref': 'منعرف', 'bta3rfo|bta3rfou|bt3rfo': 'بتعرفو', 'bya3rfo|by3rfo': 'بيعرفو',
    'fhemet|fhimit|fhemit|fhemt|fhimt': 'فهمت', 'fhemtak|fhemtik': 'فهمتك', 'fhemte|fhemti': 'فهمتي',
    'fahem|fehem|fhem': 'فاهم', 'fahme|fehme': 'فاهمة', 'ma fhemet': 'ما فهمت',
    '2ellak|ellak|2ilak|2elak|2ellik|ellik': 'ألّك', '2oul|2ol|oul|ol|2ouli|ouli|2oli': 'أول', '2elt|elt|2ilt|ilt': 'ألت',
    '2al|2aal|aal': 'آل', '2alet|2alit|alet': 'آلت', '2alo|2alou|alo': 'آلو',
    'ejit|ejeet|ijit|jit|jeet': 'إجيت', 'eje|ija|eja|ejaa': 'إجا', 'ejet|ejit|ijet': 'إجت', 'ejo|ejou|ijo': 'إجو',
    'ta3a|ta3e|ta3o|ta3ou|t3a': 'تعا', 'ta3i|ta3e': 'تعي', 'ta3o|ta3ou|ta3u': 'تعو',
    'rou7|rouh|roo7|rooh|ru7|rouh': 'روح', 'rou7e|rou7i|roo7i': 'روحي', 'rou7o|rou7ou': 'روحو',
    're7et|re7it|ri7et|rehet|ri7it': 'رحت', 'ra7|rah|ra7a': 'رح', 'ra7et|ra7it|rahet': 'راحت',
    'khod|5od|khoud|5oud': 'خود', 'khode|5ode|khodi|5odi': 'خودي', '3ati|3atini|3ateni|3tini': 'عطيني', '3ata|3te': 'عطى',
    '3tini|3teeni': 'عطيني', '3atik|3ateek': 'عطيك',
    '2e3od|2e3ood|o3od|2o3od|e3od': 'أعود', 'nam|nem|neem|naam': 'نام', 'nemet|nimit|nemit': 'نمت',
    'fi2|fee2|fe2': 'فيئ', 'fiq': 'فيق', 'f2et|fe2et|fi2it': 'فئت', 'shouf|shuf|chouf|shoof|chuf': 'شوف', 'shoufe|shufi|choufi': 'شوفي',
    'shefet|shefit|shift|shoft|shuft|chefet': 'شفت', 'sma3|sme3|sma3e': 'سمع', 'sme3et|sme3it|smi3it|sme3t': 'سمعت',
    '7ake|7aki|haki|7akee|hake': 'حكي', '7keet|7kit|7akit|hkit|7keyt': 'حكيت', 'e7ke|e7ki|ehke|ehki|i7ki': 'إحكي',
    'ektob|ktob|iktob': 'اكتوب', 'ktabet|ktabit|katabet': 'كتبت', '2ara|2ra|ara|e2ra': 'إئرا',
    'koul|kool': 'كول', 'akalet|akalit|akalt': 'أكلت', 'shrab|shrob|chrab': 'اشراب', 'shrebet|shribit|shrebt': 'شربت',
    '3emel|3mel|3imil|3emil': 'عمل', '3mol|3emol|3mool|3mool': 'عمول', 'na3mel|n3mel|na3mil': 'نعمل',
    'bi3mel|by3mel|bya3mel|bi3mil': 'بيعمل', 'ba3mel|b3mel|ba3mil': 'بعمل', 'bta3mel|bt3mel|bta3mil': 'بتعمل',
    'ta3mel|t3mel|ta3mil': 'تعمل', '3melet|3milit|3emlet|3melt': 'عملت', 'mna3mel|mn3mel': 'منعمل',
    't3emelli|t3emeli|ta3mele|t3mele|t3melle|ta3melle': 'تعمل لي', 't3emello|t3mello': 'تعمل لو',
    'jib|jeeb|jiib': 'جيب', 'jibe|jibi|jeebi': 'جيبي', 'jebet|jibit|jebt': 'جبت',
    '7ot|7ott|hot|hott|7ut': 'حطّ', '7otte|7otti|hotti': 'حطّي', '7atet|7atit|7atayt': 'حطّيت',
    'ftah|fta7|fte7|ftah|ifta7|fta7': 'فتح', 'fta7e|fte7e|fta7i|fte7i': 'فتحي', 'fata7et|fata7it|fta7t': 'فتحت',
    'sakker|sakkir|sakar|saker|sakir': 'سكّر', 'sakkre|sakkri|sakre': 'سكّري', 'sakkaret|sakkarit|sakart': 'سكّرت',
    'taffe|taffi|tafi|tafe|tfe|tfi|tafee|taffee': 'طفّي', 'taffo|taffou|tafo': 'طفّو', 'taffet|taffit|tafet|tafayt|taffayt': 'طفّيت',
    'sha8el|sha8il|shaghel|shaghil|shaghghel|cha8el|chaghel|shagel': 'شغّل', 'sha8le|sha8li|shaghli': 'شغّلي',
    'sha8alet|shaghalet|sha8alit|shaghalt|sha8alt': 'شغّلت', 'sha8el|shaghel': 'شغّل',
    'dawwe|dawwi|dawe|dawi': 'ضوّي', 'dawwet|dawwit|dawayt': 'ضوّيت', '3alle|3alli|3ali|3allee': 'علّي', '3allet|3allit|3alayt': 'علّيت',
    'watte|watti|wattee|watiy': 'وطّي', 'wattet|wattit|watayt': 'وطّيت', 'zid|zeed|ziid|zeid': 'زيد', 'zidet|zidit|zedt': 'زدت',
    '2alel|alel|2allel|2allil|allil': 'ألّل', '2allet|2allit|2alalt': 'ألّلت', 'ghayyer|8ayyer|ghayer|8ayer': 'غيّر',
    'wa2ef|wa2if|wa22ef|wa22if|wakef': 'وأّف', 'wa2fet|wa2afet|wa22fet': 'وأّفت', 'kammel|kamel|kammil': 'كمّل',
    'ba3et|ba3at|b3at': 'بعت', 'ba3atle|ba3atli|b3atli': 'بعتلي', 'etasel|ittasel|ittasil|etassel': 'إتّصل',
    'mashi|meshi|mesheh|mashe|mech|meche|machi|machee|meshe|mashy|mashii': 'ماشي',
    'wade3|wad3|wadi3|wade3': 'وضع', 'jaw|jaww|jow': 'جو',
    # Home and devices
    'daw|daww|dou|daou|daoo|dawou|dawe': 'ضوّ', 'dwe|dwayye|dwaye|adwiye': 'ضوّة',
    'salon|salone|saloun|saloon|salown': 'صالون', 'matbakh|matba5|matbakhh|matba7': 'مطبخ',
    'oda|2oda|ouda|2ouda|odaa|2odah': 'أوضة', 'hammam|7ammam|7emmem|hemmem|7ammem|hamam': 'حمّام',
    'beit|bayt|bet|beyt|bait|beet': 'بيت', 'bab|beb|baab': 'باب', 'shebbek|shebbak|shibbek|chebbek|shibbak|shebbeik': 'شبّاك',
    'mkayyef|mkayef|mkeyyef|mkayif|mkayyif|mkeyef|mkayyf': 'مكيّف', 'tv|tele|tilfizyon|telfizion': 'تلفزيون',
    'sakhan|sa5an|skhan|s5an|sakhkhan|sa55an': 'سخّان', 'ghasele|ghassele|8assele|8asele|ghaseleh': 'غسّالة',
    'barrad|barred|berrad|barad|bared|birrad': 'برّاد', 'jlaye|jellaye|jallaye|jlayi': 'جلّاية',
    'fern|forn|furn|fren': 'فرن', 'ghaz|8az|gaz': 'غاز', 'mayy|may|mai|mayye|mayeh|mayya|moy': 'ميّ',
    'kahraba|kahraba2|kahrabe|kahrba': 'كهربا', 'mawtor|motor|moteur|motour': 'موتور', 'ishtirak|eshtirak|ichtirak': 'اشتراك',
    'ta2a': 'طاءة', 'taqa': 'طاقة', 'bataria|battariye|batariye': 'بطّاريّة', 'telephone|telefon|talifon|telfon|telephon': 'تلفون',
    'mobile|mobayl|mobil': 'موبايل', 'computer|kombyouter|kompyouter': 'كمبيوتر', 'laptop': 'لابتوب',
    'internet|internit': 'إنترنت', 'wifi': 'واي فاي', 'net': 'نت', 'remote|rimot': 'ريموت',
    'sayyara|sayara|siyara|siyyara|sayyare': 'سيّارة', 'taree2|tari2|tri2': 'طريئ', 'tariq': 'طريق',
    'mahal|ma7al|ma7all|ma7el': 'محل', 'madrase|madrasi|madraseh': 'مدرسة', 'shoghl|sheghel|sheghl|shoghol|choghl|shughl': 'شغل',
    'jem3a|jam3a|jeme3a': 'جامعة', 'sou2|su2': 'سوء', 'souk|souq': 'سوق', 'mostashfa|mustashfa|mestashfa': 'مستشفى',
    'ghorfe|ghorfi|8orfe|ghurfe': 'غرفة', 'takhet|ta5et|takht|ta5t': 'تخت', 'tawle|tawli|tawleh|tawla': 'طاولة',
    'korse|korsi|kirse|kirsi': 'كرسي', 'kanabaye|kanabay|kanaba': 'كنباية', 'sotou7|stou7|satah': 'سطوح',
    'balcon|balcone|balkon|balcony': 'بلكون', 'jnayne|jnayni|jneyne|jnaine': 'جنينة', 'garaj|garage|karaj': 'كراج',
    'dara|daraj|drej|darej': 'درج', 'ascenseur|asanseur|asansor': 'أسانسور', 'bawwabe|bawebe|bawwebe': 'بوّابة',
    'stor|sitar|sitara|star': 'ستارة', 'bosta|busta': 'بوسطة',
    # Food and drink
    'akel|akl|akil|akul': 'أكل', '2ahwe|ahwe|2ahwi|ahwi|2ahweh|ahweh|2ahwa': 'أهوة', 'shay|chai|shai|chay|shaii': 'شاي',
    'khebez|khebz|5ebez|5ebz|khobz|5obz': 'خبز', 'ghada|8ada|ghadaa': 'غدا', '3asha|3acha|3ashaa': 'عشا',
    'trwi2a|terwi2a|trwee2a|terwee2a': 'ترويئة', 'jou3an|jaw3an|jo3an|jou3en|ju3an': 'جوعان', 'jou3ane|jou3ani|jaw3ane': 'جوعانة',
    '3atshan|3atchan|3atshen': 'عطشان', '3atshane|3atshani|3atchane': 'عطشانة', 'sokkar|sekkar|sukkar|sikkar': 'سكّر',
    'mel7|melh|mil7': 'ملح', 'zet|zeit|zayt': 'زيت', 'la7me|la7mi|lahme|la7meh': 'لحمة', 'djej|djej|jej|djaj': 'دجاج',
    'samak|samke|samak': 'سمك', 'rez|rezz|riz|roz': 'رز', 'batata|batate': 'بطاطا', 'banadoura|banadora|bandoura': 'بندورة',
    'khyar|5yar|khiyar|5iyar': 'خيار', 'basal|bassal': 'بصل', 'toum|toom|tum': 'توم', 'jebne|jebni|jibne|jebneh': 'جبنة',
    'laban|labne|labne|labneh': 'لبن', '7alib|halib|7aleeb|7aleb': 'حليب', 'bayd|beid|beyd|bayda': 'بيض',
    'man2oushe|man2ouche|man2oushi': 'منأوشة', 'mankoushe': 'منكوشة', 'tabbouleh|tabboule|tabouleh|tabule': 'تبّولة',
    'kebbe|kibbe|kebbeh|kibbeh': 'كبّة', 'fattoush|fatoush|fattouch': 'فتّوش', 'hummus|hommos|hommus|7ommos': 'حمّص',
    'falafel|flafel': 'فلافل', 'shawarma|chawarma': 'شاورما', 'knefe|knafe|knefeh|knafeh': 'كنافة', '7elwe|helwe|7elwi': 'حلوة',
    'fawekeh|fawakeh|fawake': 'فواكه', 'tefe7a|tiffe7a|tefe7': 'تفّاحة', 'mawz|moz|mouz': 'موز', 'borto2al|bortu2al|bourto2al': 'برتؤال',
    # People and family
    'mama|mame|mamii': 'ماما', 'baba|babe|babii': 'بابا', 'bayye|bayyi|bayy|bayi': 'بيّي', 'emme|emmi|immi|imme|emmii': 'إمّي',
    'khayye|5ayye|khayyi|5ayyi|khayy|khaye': 'خيّي', 'ekhte|ekhti|ikhti|e5te|e5ti|ikhte|khte': 'إختي',
    '7abibi|habibi|7abibe|7abeebe|habibe': 'حبيبي', '7abibte|habibti|7abibti|7abeebte|habibte': 'حبيبتي',
    '7abib|habib|7abeeb': 'حبيب', 'sa7be|sa7bi|sahbi|sa7eb|sa7ib': 'صاحبي', 'sa7ebte|sa7ebti|sa7bte': 'صاحبتي',
    'rfi2|rfee2|rfi2e|rfi2i|rfee2e|rfii2': 'رفيئي', 'rfi2a|rfee2a|rfi2te': 'رفيئتي', 'sabe|sabi|sabee': 'صبي',
    'benet|bent|bint|binit|bineet': 'بنت', 'walad|weled|wald': 'ولد', 'wled|wlad|wleed|ewled': 'ولاد',
    'zalame|zalami|zalameh|zalmeh': 'زلمة', 'mara|mra|marah': 'مرا', '3ayle|3ayli|3eile|3eyle|3ayleh': 'عيلة',
    'jedde|jeddi|jiddi|jedo|jeddo|jiddo': 'جدّي', 'teta|tete|teyta|tata': 'تيتا', '3ammo|3amo|3am': 'عمّو',
    '3amto|3ameto|3amte|3amti': 'عمتو', 'khalo|5alo|khali|5ali': 'خالو', 'khalto|5alto|khalte|5alte': 'خالتو',
    'jar|jaar|jeer': 'جار', 'jiran|jeeran|jiraan': 'جيران', 'nes|nas|naas|nass': 'ناس', 'ensen|insen|insan|ensan': 'إنسان',
    'doktor|doctor|dokter|dktor': 'دكتور', 'mo3allem|m3allem|mu3allem|m3alem': 'معلّم', 'mo3allme|m3allme|m3almi': 'معلّمة',
    # Adjectives and feelings
    'mabsout|mabsot|mabsoot|mabsut': 'مبسوط', 'mabsouta|mabsota|mabsoota': 'مبسوطة', 'za3lan|za3len|za3laan': 'زعلان',
    'za3lane|za3lani|za3lene': 'زعلانة', 'ta3ban|ta3ben|ta3baan': 'تعبان', 'ta3bane|ta3bani|ta3bene': 'تعبانة',
    'mari2|mreed|marid|mariid|mreed': 'مريض', 'mariida|mareeda|mrida': 'مريضة', 'far7an|farhan|far7en': 'فرحان',
    'far7ane|farhane|far7ani': 'فرحانة', 'khayef|5ayef|khayif|5ayif': 'خايف', 'khayfe|5ayfe|khayfi': 'خايفة',
    'me3assab|m3assab|me3asab|m3asab': 'معصّب', 'me3assbe|m3assbe|m3asbe': 'معصّبة', 'mashghoul|mashghul|mash8oul|mach8oul': 'مشغول',
    'mashghoule|mash8oule|mashghouli': 'مشغولة', 'zahlan|zahlen': 'زهقان', 'na3san|na3sen|na3saan': 'نعسان', 'na3sane|na3sani': 'نعسانة',
    '3azim|3azeem|3azem|3aziim': 'عظيم', '7elo|helo|7ilo|7ilou|7elou|helou|7lo': 'حلو', '7elwe|7elwi|helwe|7elweh|helwi': 'حلوة',
    'kbir|kbeer|kbiir|kbir': 'كبير', 'kbire|kbiri|kbeere|kbeeri': 'كبيرة', 'zghir|zgheer|z8ir|sghir|s8ir|zghiir|zgheir': 'زغير',
    'zghire|zghiri|z8ire|sghire|zgheere': 'زغيرة', 'jdid|jdeed|jdiid|jadid|jdeid': 'جديد', 'jdide|jdidi|jdeede|jdeedi': 'جديدة',
    '2adim|adeem|2adeem|2adiim|adim': 'أديم', '2adime|2adimi|2adeeme': 'أديمة', 'sare3|saree3|sari3|sarii3': 'سريع',
    'bati2|batee2|batii2': 'بطيء', 'sokhon|so5on|sekhen|se5en|sokhen|sukhn|s5on': 'سخن', 'sokhne|so5ne|sekhne|se5ne': 'سخنة',
    'bared|bered|berid|baared': 'بارد', 'barde|berde|bardi|berdi': 'باردة', 'bard|bared': 'برد', '7ami|hami|7amii|7aami': 'حامي',
    '7amye|7amyi|hamye': 'حامية', '7ar|har|7arr': 'حر', 'shob|shoub|choub|shawb': 'شوب', '3ali|3ale|3aali|3alii': 'عالي',
    '3alye|3alyi|3aliye': 'عالية', 'wati|wate|waati|watii': 'واطي', 'watye|watyi|watiye': 'واطية', 'ghali|8ali|ghaali|ghalii': 'غالي',
    'ghalye|8alye|ghalyi': 'غالية', 'rkhis|r5is|rkhees|rkhiis|rkheis': 'رخيص', 'rkhisa|r5isa|rkheesa': 'رخيصة',
    'ndif|ndeef|ndiif|nadif|ndeif': 'نضيف', 'ndife|ndifi|ndeefe': 'نضيفة', 'wesekh|wesikh|wese5|wsekh|wsikh': 'وسخ', 'weskha|wes5a|weskhe': 'وسخة',
    'tawil|taweel|tawiil|taweel': 'طويل', 'tawile|tawili|taweele': 'طويلة', '2asir|2aseer|2asiir|asir|2seer': 'أصير',
    '2asire|2asiri|2aseere': 'أصيرة', '2arib|2areeb|2ariib|areeb|2reeb': 'أريب', '2aribe|2aribi|2areebe': 'أريبة',
    'b3id|b3eed|b3iid|b3eid|ba3id': 'بعيد', 'b3ide|b3idi|b3eede': 'بعيدة', 'sahl|sahel|sehel': 'سهل', 'sahle|sahli|sehle': 'سهلة',
    's3ib|s3eeb|s3iib|sa3eb|s3eib': 'صعب', 's3ibe|s3ibi|s3eebe': 'صعبة', 'hadi|hade|hadii|hedi': 'هادي', 'hadye|hadyi|hadiye': 'هادية',
    'sari3|saree3': 'سريع', 'ghalban|8alban|ghalben': 'غلبان', 'fadi|fade|fadii': 'فاضي', 'fadye|fadyi|fadiye': 'فاضية',
    'malyan|malyen|malyaan': 'مليان', 'malyane|malyani|malyeni': 'مليانة', 'jehez|jehiz|jahez|jahiz': 'جاهز', 'jehze|jahze|jehzi': 'جاهزة',
    'mawjoud|mawjood|mawjud|mawjoud': 'موجود', 'mawjoude|mawjoodi|mawjudi': 'موجودة', 'maftou7|maftouh|maftoo7|maftu7': 'مفتوح',
    'maftou7a|maftouha|maftoo7a': 'مفتوحة', 'msakkar|msakar|mskkar': 'مسكّر', 'msakkra|msakkara|msakra': 'مسكّرة',
    'shaghghel|sha8ghel|sha88el': 'شغّال', 'shaghal|sha8al|sha88al|shaghgal': 'شغّال', 'shaghale|sha8ale|sha88ale': 'شغّالة',
    'mtaffa|mtafa|mtaffe|mtafe|mtaffi': 'مطفّى', 'mtaffaye|mtafaye|mtaffaye': 'مطفّاية', 'khaleh|khali|khalye|5alye': 'خالية',
    # Time and weather
    'bokra|boukra|bukra|bokra': 'بكرا', 'lyom|lyoum|lyawm|elyom|elyoum|lyom': 'اليوم', 'yom|yawm|yowm|youm': 'يوم',
    'mbere7|mbare7|embere7|mbereh|mbareh|imbere7': 'مبارح', 'msa|masa|mase|masaa': 'مسا', 'sabah|saba7|sabe7|sabeh|sabaa7': 'صباح',
    'kheir|khair|5eir|5air|kheyr|khayr': 'خير', 'lel|leil|layl|leyl': 'ليل', 'nhar|nhaar|nahar|nhaar': 'نهار',
    'se3a|sa3a|saa3a|se3ah|sa3ah|sei3a': 'ساعة', 'se3at|sa3at': 'ساعات', 'da2i2a|d2i2a|di2i2a|d2ee2a|d2i2i': 'دئيئة',
    'daqiqa': 'دقيقة', 'da2aye2|d2aye2|da2ayi2|d2ayi2': 'دأايئ', 'senye|sanye|seni': 'ثانية', 'osbou3|usbou3|osboo3|osbu3': 'أسبوع',
    'jem3a|jom3a|jum3a|jem3ah': 'جمعة', 'shahr|shaher|chaher|shahar': 'شهر', 'sene|sane|sine|seneh|sana': 'سنة',
    'snin|sneen|sniin': 'سنين', 'ba3d bokra': 'بعد بكرا', 'bokra el sobo7|sobo7|sobe7|sob7': 'صبح', 'dohr|dohor|doher|duhr': 'ضهر',
    '3asr|3aser|3asir': 'عصر', 'maghreb|ma8reb|maghrib': 'مغرب', '3isha|3esha|3ishaa': 'عشا', 'nos|noss|nus|nuss': 'نص',
    'rob3|rob3a|rub3|rub3a': 'ربع', 'telt|tilt|tolt': 'تلت', 'badri|badre|bedre|bakir|bakkir': 'بكّير', 'met2akher|mt2akher|mit2akher': 'متأخّر',
    'ta2s|ta2es|ta2ss|ta2is': 'طأس', 'taqs': 'طقس', '7arara|harara|7araara': 'حرارة', 'daraje|darajeh|daraji|daraja': 'درجة',
    'nar|naar': 'نار', 'hawa|hawe|hawaa': 'هوا', 'shams|chams|shames|shamss': 'شمس', '2amar|amar|2amr|2amer': 'أمر',
    'matar|mtar|matr': 'مطر', 'shete|shite|shiti|cheti|shete': 'شتي', 'talj|telj|thalj|talej': 'تلج', 'ghaym|gheim|ghayme|8aym': 'غيم',
    'rih|ri7|ree7|reeh': 'ريح', 'ratb|rateb|roteb|rtoube': 'رطوبة', 'sayf|seif|seyf|saif': 'صيف', 'rabi3|rabee3': 'ربيع', 'kharif|5arif|khareef': 'خريف',
    # Numbers
    'wa7ad|wa7ed|wahad|wahed|wa7id|wa7d': 'واحد', 'wa7de|wa7di|wahde|we7de': 'وحدة', 'tnen|tnein|tneen|tnayn|tnein': 'تنين',
    'tlete|tleti|tlate|tlat|tleteh|tlati|tlat': 'تلاتة', 'arb3a|arba3a|arb3ah|arba3ah|arb3': 'أربعة', 'khamse|5amse|khamsi|5amsi|khamseh': 'خمسة',
    'sette|setti|sitte|sitti|seteh': 'ستة', 'sab3a|sab3ah|sab3': 'سبعة', 'tmene|tmeni|tmane|tmeneh|tmani': 'تمانة', 'tes3a|tis3a|tes3ah': 'تسعة',
    '3ashra|3ashara|3achra|3ashrah': 'عشرة', '7da3sh|7da3ash|7eda3sh|hda3sh': 'حدعش', 'tna3sh|tna3ash|etna3sh': 'طنعش',
    '3eshrin|3ishrin|3eshreen|3echrin': 'عشرين', 'tletin|tlateen|tletiin': 'تلاتين', 'mit|miyye|mia|miyeh|mieh|miyya|miye': 'مية',
    'alf|alef|elf': 'ألف', 'nos|noss': 'نص', 'awwal|awal|awwel|awel': 'أوّل', 'tene|teni|taani|tani|teneh': 'تاني', 'ekher|akher|a5er|e5er|akhir': 'آخر',
    # Misc verbs and words
    'bshouf|bchouf|bshuf': 'بشوف', 'btshouf|btchouf': 'بتشوف', 'bisma3|bysma3|besma3': 'بيسمع', 'bsma3|bisma3': 'بسمع',
    'bye2dar|by2dar|bi2dar|bye2der|bi2der': 'بيئدر', 'be2dar|b2dar|be2der|b2der|ba2dar': 'بئدر', 'bte2dar|bt2dar|bte2der|bt2der': 'بتئدر',
    'mne2dar|mn2dar|mne2der': 'منئدر', '2derna|2dirna': 'أدرنا', 'ma 2dert|2dert|2dirt': 'أدرت', '2der|2dir|2eder': 'أدر',
    'bi7eb|by7eb|bi7ib|by7ib|bi7ebb': 'بيحب', 'b7eb|b7ib|ba7eb|ba7ib|b7ebb': 'بحب', 'bt7eb|bt7ib|bte7eb|bte7ib': 'بتحب',
    'mn7eb|mn7ib|mne7eb': 'منحب', '7abbet|7abbit|7abayt|7abeit': 'حبّيت', 'bye3ref|by3ref': 'بيعرف',
    'biji|byji|bije|byje|bijee': 'بيجي', 'bji|bje|beji|bejee': 'بجي', 'btji|btje|bteje': 'بتجي', 'mnji|mnje': 'منجي',
    'birou7|byrou7|biroo7|birouh|byrouh': 'بيروح', 'brou7|broo7|brouh|berou7': 'بروح', 'btrou7|btroo7|btrouh': 'بتروح', 'mnrou7|mnroo7': 'منروح',
    'bi2oul|by2oul|bi2ol|by2ol|bi2ul': 'بيئول', 'b2oul|b2ol|be2oul|b2ul': 'بئول', 'bt2oul|bt2ol|bte2oul': 'بتئول', 'mn2oul|mn2ol': 'منئول',
    'byekol|biekol|byekil|bi2kol|byakol': 'بياكل', 'bekol|bekil|b2kol|bakol': 'باكل', 'btekol|btekil|bt2kol': 'بتاكل', 'mnekol|mnekil': 'مناكل',
    'byeshrab|bieshrab|byishrab|bishrab': 'بيشرب', 'beshrab|bishrab|bshrab': 'بشرب', 'bteshrab|btishrab|btshrab': 'بتشرب',
    'bynem|binam|bynam|binem': 'بينام', 'bnem|bnam|benem|benam': 'بنام', 'btnem|btnam|btenem': 'بتنام',
    'byshteghel|bishteghel|byshte8el|bishte8el|byshtighil': 'بيشتغل', 'bshteghel|bshte8el|beshteghel|bishtighil': 'بشتغل',
    'btshteghel|btshte8el|bteshteghel': 'بتشتغل', 'byeshtghel|bieshtghel': 'بيشتغل',
    'bet3allam|bit3allam|bt3allam|bet3alam': 'بتعلّم', 'byet3allam|biet3allam|byt3allam': 'بيتعلّم',
    'bade namm|bade nem': 'بدّي نام', 'lezem rou7': 'لازم روح',
    'ra7 rou7|ra7 roo7': 'رح روح', 'ra7 ejee|ra7 eje|ra7 ejii': 'رح إجي',
    'jarreb|jarrib|jareb|jarib': 'جرّب', 'jarrabet|jarrabit|jarabt': 'جرّبت', 'rajje3|raje3|rajji3': 'رجّع', 'rje3|rjaa3|rja3|rjee3': 'رجاع',
    'rje3et|rje3it|rja3t|rje3t': 'رجعت', 'stanna|stana|istanna|stannaa': 'ستنّى', 'stannet|stannit|stannayt|stanayt': 'ستنّيت',
    'natour|nator|natoor|natur': 'ناطور', 'dakhal|da5al|dakhel|da5el': 'دخل', 'fout|foot|fut|fot': 'فوت', 'fouti|footi|fute': 'فوتي',
    'tla3|tla3|tlaa3|tle3': 'طلاع', 'tle3et|tle3it|tla3t|tle3t': 'طلعت', 'nzal|nzel|nzaal|nzil': 'نزال', 'nzelet|nzilit|nzelt|nzilt': 'نزلت',
    'ghasal|ghassal|8asal|8assal': 'غسّل', 'ghassalet|ghasalit|8asalt': 'غسّلت', 'naddaf|nadaf|naddef|nadef': 'نضّف', 'naddafet|naddafit|nadaft': 'نضّفت',
    'tabakh|taba5|tbokh|tbo5|tabbakh|tabbekh': 'طبخ', 'tabakhet|tabakhit|tabakht|taba5t': 'طبخت', 'eshtara|ishtara|shtara|chtara': 'اشترى',
    'eshtaret|ishtarit|shtaret|shtareit|chtaret': 'اشتريت', 'dafa3|dafe3|daffa3': 'دفع', 'dafa3et|dafa3it|dafa3t': 'دفعت',
    'seket|skot|skoot|skut|sket': 'سكوت', 'seketet|skitit|sekett|skett': 'سكتّ', 'de7ek|de7ik|dehek|d7ak': 'ضحك', 'de7ket|de7kit|de7ekt': 'ضحكت',
    'beke|beki|bake|biki': 'بكي', 'bkeet|bkit|bekit|bakayt': 'بكيت', 'la3ab|l3ab|le3eb|l3eb': 'لعب', 'le3bet|l3ebit|la3abt|le3ebt': 'لعبت',
    'mashi|meshi': 'ماشي', 'meshet|mshit|meshit|mshet': 'مشيت', 'wesel|wesil|wasal|wosel': 'وصل', 'weslet|wesilt|waslt|wselt': 'وصلت',
    'fel|fil|fal|fol': 'فل', 'fallet|fallit|falleit|falayt': 'فلّيت', 'tarak|terek|trok|trouk': 'ترك', 'tarket|tarakit|tarakt': 'تركت',
    'ltamet|ltamit|lta2ayt|lta2et': 'التئيت', 'khabbar|5abbar|khaber|khabbir': 'خبّر', 'khabbaret|khabbarit|khabarit|khabbart': 'خبّرت',
    'khabbir|5abbir|khabrni|5abrni|khabberni|5abberni': 'خبّرني', 'nokte|nokta|nikte|nukta|nokteh': 'نكتة', 'khabar|5abar|khabr': 'خبر',
    'akhbar|a5bar|akhbaar': 'أخبار', 'sa2al|sa2il|se2el|sa2el': 'سأل', 'sa2alt|sa2alet|sa2alit': 'سألت', 'sou2al|su2al|soual|so2al': 'سؤال',
    'jaweb|jawib|jawab|jaweb': 'جاوب', 'jawabet|jawabit|jawabt': 'جاوبت', 'jawab|jaweb|jawaab': 'جواب', 'fekra|fikra|fekreh|fikre': 'فكرة',
    'ra2e|ra2i|ra2ye|ra2yi|ra2ee': 'رأيي', 'ra2yak|ra2yik': 'رأيك', 'mashkle|mashkal|moshkle|mishkle|moshkila': 'مشكلة',
    'mashakel|mashakil|mashekel': 'مشاكل', 'wa2t|wa2et|wa2it': 'وأت', 'waqt': 'وقت', 'sar|saar|sarr': 'صار', 'saret|sarit|sart': 'صارت', 'saro|sarou': 'صارو',
    'bisir|bysir|biseer|byseer|bsir|bseer': 'بيصير', 'btsir|btseer|bteseer': 'بتصير', 'mnsir|mnseer': 'منصير', 'sir|seer|siir': 'صير',
    'kamen|kaman|kamaan|kmen': 'كمان', 'lissa|lessa|lisa|lesa|lsa': 'لسّا', 'ba3dni|ba3dne|ba3dnee|ba3dani': 'بعدني', 'ba3dak|ba3dik': 'بعدك',
    'ba3do|ba3da|ba3don|ba3dna': 'بعدو', 'abadan': 'أبداً', 'bil 3aks|bel 3aks|3aks': 'عكس', 'heke|hekeh|hayke': 'هيكي',
    'bzyede|bzyedi|bziyede|bzyade|bziyade': 'بزيادة', 'bass hek|bas hek': 'بس هيك', 'ya3ne hek': 'يعني هيك',
    'kaza|kazaa|keza': 'كذا', 'ta2riban|ta2reeban|t2riban': 'تأريباً', 'bidoun|bdoun|bidun|bdun|bidoon': 'بدون',
    'ghayr|gher|gheir|8ayr|8er|8eir': 'غير', 'nafs|nafes|nafss': 'نفس', 'mitel|mitl|metel|metl|mitil': 'متل', 'mitl ma|metel ma': 'متل ما',
    'ya3tike|ya3tikee': 'يعطيكي', 'ya3tikon': 'يعطيكن', 'allah ysalmak|ysalmak': 'الله يسلمك', 'allah ykhalik|ykhalik|ykhallik|y5alik': 'الله يخلّيك',
    'wla|wlak|wlek|wlik|wleh': 'ولك', 'yaa|yaaa': 'يا', 'ya zalame': 'يا زلمة', 'ya 3ammo': 'يا عمّو', 'ya 7abibi': 'يا حبيبي',
    'ya3ne shou|ya3ni shou': 'يعني شو', 'wlo|wlou|wlow': 'ولو', 'ba2a|ba2aa': 'بأى', 'b2a': 'بأى', 'ba2e|ba2i|be2e': 'بائي',
    'awwal shi|awal shi': 'أوّل شي', 'ekher shi|akher shi': 'آخر شي', 'kel shi|kil shi|kol shi': 'كل شي', 'wala shi|wla shi': 'ولا شي',
    'wala|wla|walaa': 'ولا', 'eh wala|e wala': 'إيه ولا', 'ma3na|ma3nah|ma3neh': 'معنى', 'ma3lish': 'معلش',
    'lazem|lezem': 'لازم', 'ma3 ba3ed|ma3 ba3d': 'مع بعض', 'ba3ed|ba3ed': 'بعض', 'so2al': 'سؤال', 'jawab': 'جواب',
    'lwade3|elwade3|lwad3': 'الوضع', 'lhal|elhal|l7al|el7al': 'الحال', 'lbeit|elbeit|lbayt|elbayt': 'البيت', 'ldaw|eldaw|ldaww|eldaww': 'الضوّ',
    'lsalon|elsalon|essalon': 'الصالون', 'lmatbakh|elmatbakh|lmatba5': 'المطبخ', 'lyom|elyom': 'اليوم', 'lmkayyef|elmkayyef|lmkayef': 'المكيّف',
})

PREFIXES = [
    ('wel', 'وال'), ('wal', 'وال'), ('bel', 'بال'), ('bil', 'بال'), ('bl', 'بال'), ('3al', 'عال'),
    ('lal', 'لل'), ('el', 'ال'), ('al', 'ال'), ('il', 'ال'), ('ma', 'ما '), ('ya', 'يا '),
    ('l', 'ال'), ('w', 'و'), ('b', 'ب'), ('la', 'ل'), ('t', 'ت'), ('n', 'ن'), ('y', 'ي'),
]
SUFFIXES = [
    ('kon', 'كن'), ('hon', 'هن'), ('na', 'نا'), ('ha', 'ا'), ('ak', 'ك'), ('ik', 'ك'), ('ek', 'ك'),
    ('on', 'ن'), ('o', 'و'), ('e', 'ي'), ('i', 'ي'),
]

CONSONANTS = {
    'b': 'ب', 't': 'ت', 'j': 'ج', 'd': 'د', 'r': 'ر', 'z': 'ز', 's': 'س', 'f': 'ف', 'q': 'ق', 'k': 'ك',
    'l': 'ل', 'm': 'م', 'n': 'ن', 'h': 'ه', 'w': 'و', 'y': 'ي', 'g': 'غ', 'p': 'ب', 'v': 'ف', 'c': 'ك',
    'x': 'كس', '2': 'ء', '3': 'ع', '5': 'خ', '6': 'ط', '7': 'ح', '8': 'غ', '9': 'ص', "'": 'ء',
}
DIGRAPHS = {
    'sh': 'ش', 'ch': 'ش', 'kh': 'خ', 'gh': 'غ', 'th': 'ث', 'dh': 'ذ', "3'": 'غ', "7'": 'خ',
    'ou': 'و', 'oo': 'و', 'uu': 'و', 'ee': 'ي', 'ii': 'ي', 'aa': 'ا',
    'ai': 'ي', 'ay': 'ي', 'ei': 'ي', 'ey': 'ي', 'aw': 'و', 'au': 'و',
}
VOWELS = set('aeiou')
INITIAL_VOWEL = {'a': 'أ', 'e': 'إ', 'i': 'إ', 'o': 'أو', 'u': 'أو'}
FINAL_VOWEL = {'a': 'ا', 'e': 'ة', 'i': 'ي', 'o': 'و', 'u': 'و'}

LATIN = re.compile(r'[a-z]')
# "el", "bel", "w" and friends are written as separate Arabizi words but attach
# to the following word in Arabic script.
CLITIC = re.compile(r'(?<![ء-ْ])(وال|بال|عال|لل|ال|و) (?=[ء-ي])')
TOKEN = re.compile(r"[A-Za-z0-9'ء-يً-ْ٠-٩]+(?:-[A-Za-z0-9']+)*")
PUNCTUATION = str.maketrans({'?': '؟', ',': '،', ';': '؛'})


def hamza(word, i):
    """The hamza seat depends on the neighbouring vowels."""
    before = word[i - 1] if i else ''
    after = word[i + 1] if i + 1 < len(word) else ''
    if i == 0:
        return 'إ' if after in ('e', 'i') else 'أ'
    if before in ('e', 'i', 'y') or after in ('e', 'i'):
        return 'ئ'
    if before in ('o', 'u') or after in ('o', 'u'):
        return 'ؤ'
    if before == 'a' or after == 'a':
        return 'أ'
    return 'ء'


def spell(word):
    """Letter-by-letter fallback for a lowercase word not in the dictionary."""
    out = []
    i, n = 0, len(word)
    while i < n:
        pair = word[i:i + 2]
        if pair in DIGRAPHS and not (i == 0 and pair in ('ai', 'ay', 'ei', 'ey', 'aw', 'au')):
            out.append(DIGRAPHS[pair])
            i += 2
            continue
        c = word[i]
        if c in VOWELS:
            if i == 0:
                out.append(INITIAL_VOWEL[c])
            elif i == n - 2 and word[i + 1] == 'h' and c in 'ae':
                out.append('ة')  # "-eh" / "-ah" endings are the feminine ة
                i += 2
                continue
            elif i == n - 1:
                out.append(FINAL_VOWEL[c])
            # A single vowel inside a word is a short vowel: not written.
            i += 1
            continue
        if c in CONSONANTS:
            if i + 1 < n and word[i + 1] == c:
                out.append(CONSONANTS[c] + SHADDA)  # doubled consonant
                i += 2
                continue
            out.append(hamza(word, i) if c in ('2', "'") else CONSONANTS[c])
            i += 1
            continue
        out.append(c)
        i += 1
    return ''.join(out).replace('أا', 'آ')


def lookup(word, table):
    """Dictionary match, directly or through a known prefix or suffix."""
    if word in table:
        return table[word]
    for prefix, arabic in PREFIXES:
        rest = word[len(prefix):]
        if word.startswith(prefix) and len(rest) >= 2 and rest in table:
            return arabic + table[rest]
    for suffix, arabic in SUFFIXES:
        stem = word[:-len(suffix)]
        if word.endswith(suffix) and len(stem) >= 2 and stem in table:
            return table[stem] + arabic
    for prefix, p_arabic in PREFIXES:
        for suffix, s_arabic in SUFFIXES:
            stem = word[len(prefix):-len(suffix)]
            if word.startswith(prefix) and word.endswith(suffix) and len(stem) >= 2 and stem in table:
                return p_arabic + table[stem] + s_arabic
    return None


def convert_word(token, table=WORDS):
    """Returns (arabic, matched): matched is False when spelled by the rules."""
    word = token.lower()
    if not LATIN.search(word):
        return token, None  # digits-only or already Arabic: leave untouched
    if '-' in word:
        parts = [convert_word(part, table) for part in word.split('-') if part]
        return ''.join(arabic for arabic, _ in parts), all(m is not False for _, m in parts)
    known = lookup(word, table)
    if known is not None:
        return known, True
    return spell(word), False


def convert(text, user_words=None):
    """Convert mixed text. Words already in Arabic script pass through.

    user_words are spellings the user taught; they win over the built-in list.
    """
    table = {**WORDS, **user_words} if user_words else WORDS
    unknown, matched, latin = [], 0, 0

    def replace(match):
        nonlocal matched, latin
        token = match.group(0)
        arabic, hit = convert_word(token, table)
        if hit is None:
            return token
        latin += 1
        if hit:
            matched += 1
        elif token.lower() not in unknown:
            unknown.append(token.lower())
        return arabic

    result = CLITIC.sub(r'\1', TOKEN.sub(replace, text))
    digits_in_words = bool(re.search(r'[a-z][23578][a-z]|\b[23578][a-z]|[a-z][23578]\b', text.lower()))
    confident = latin > 0 and (digits_in_words or matched / latin >= 0.4)
    if confident or re.search(r'[ء-ي]', result):
        result = result.translate(PUNCTUATION)
    return {'arabic': result, 'confident': confident, 'unknown': unknown, 'latin_words': latin}

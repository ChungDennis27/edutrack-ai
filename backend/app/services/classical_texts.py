"""Curated sample of the DSE 12 designated 文言文 texts.

The classical Chinese originals are in the public domain. Translations, notes
and exam tips are written for this project. This is a demo set — extend with
the full 12 texts through the ingestion pipeline in production.
"""
from __future__ import annotations


CLASSICAL_TEXTS: list[dict] = [
    {
        "id": "lun-ren",
        "title": "論仁（節錄）",
        "author": "孔子及其弟子",
        "source": "《論語》",
        "dynasty": "先秦",
        "rhetoric": "語錄體；以簡潔對話直陳義理，多用對比（仁者／不仁者）。",
        "exam_tips": "常考「仁」的內涵、克己復禮的實踐，以及志士仁人的取捨。",
        "paragraphs": [
            {
                "original": "子曰：「不仁者，不可以久處約，不可以長處樂。」",
                "translation": "孔子說：「沒有仁德的人，不能長久處於貧困之中，也不能長久處於安樂之中。」",
                "notes": "約：貧困。仁者安於仁，故貧樂皆能自處。",
            },
            {
                "original": "顏淵問仁。子曰：「克己復禮為仁。一日克己復禮，天下歸仁焉。」",
                "translation": "顏淵問什麼是仁。孔子說：「約束自己，使言行合於禮，就是仁。一旦做到克己復禮，天下人都會稱許你的仁德。」",
                "notes": "克己：約束私慾。復禮：使言行合於禮。歸仁：稱許其為仁。",
            },
            {
                "original": "子曰：「志士仁人，無求生以害仁，有殺身以成仁。」",
                "translation": "孔子說：「有志之士與仁德之人，不會為了求生而損害仁德，只會犧牲生命來成全仁德。」",
                "notes": "殺身成仁：後成為成語，指為正義而犧牲。",
            },
        ],
    },
    {
        "id": "lun-xiao",
        "title": "論孝（節錄）",
        "author": "孔子及其弟子",
        "source": "《論語》",
        "dynasty": "先秦",
        "rhetoric": "語錄體；以反問、對比突顯「敬」為孝之本。",
        "exam_tips": "重點在「敬」與「養」之別，以及諫親之道。",
        "paragraphs": [
            {
                "original": "子游問孝。子曰：「今之孝者，是謂能養。至於犬馬，皆能有養；不敬，何以別乎？」",
                "translation": "子游問孝道。孔子說：「現在所謂的孝，只是說能供養父母。但狗馬也能得到飼養；如果沒有敬意，用什麼來區別呢？」",
                "notes": "養：供養。強調孝須有「敬」，非僅物質供養。",
            },
            {
                "original": "子曰：「事父母幾諫，見志不從，又敬不違，勞而不怨。」",
                "translation": "孔子說：「侍奉父母，要委婉地勸諫；若父母不聽從，仍要恭敬而不違逆，雖憂愁而不怨恨。」",
                "notes": "幾諫：委婉規勸。不違：不違逆。",
            },
        ],
    },
    {
        "id": "quan-xue",
        "title": "勸學（節錄）",
        "author": "荀子",
        "source": "《荀子》",
        "dynasty": "先秦",
        "rhetoric": "多層比喻論證；句式整齊，善用排比與對偶。",
        "exam_tips": "常考比喻論證的手法、學習的意義與持之以恆的態度。",
        "paragraphs": [
            {
                "original": "君子曰：學不可以已。青，取之於藍，而青於藍；冰，水為之，而寒於水。",
                "translation": "君子說：學習是不可以停止的。靛青從藍草中提取，卻比藍草更青；冰由水凝成，卻比水更寒冷。",
                "notes": "已：停止。青出於藍：比喻後學勝於前賢。",
            },
            {
                "original": "吾嘗終日而思矣，不如須臾之所學也；吾嘗跂而望矣，不如登高之博見也。",
                "translation": "我曾經整日思考，卻不如片刻的學習；我曾經踮起腳遠望，卻不如登上高處看得廣闊。",
                "notes": "須臾：片刻。跂：踮起腳跟。強調學習與借助外物之效。",
            },
            {
                "original": "鍥而舍之，朽木不折；鍥而不舍，金石可鏤。",
                "translation": "雕刻一下便放棄，即使朽木也折不斷；堅持雕刻而不停，金屬和石頭也能鏤刻。",
                "notes": "鍥：雕刻。鏤：雕刻。喻持之以恆。",
            },
        ],
    },
    {
        "id": "shi-shuo",
        "title": "師說（節錄）",
        "author": "韓愈",
        "source": "《昌黎先生集》",
        "dynasty": "唐",
        "rhetoric": "議論為主；善用對比（古今、貴賤、長少）與排比。",
        "exam_tips": "核心是「道之所存，師之所存」與從師問學的必要性。",
        "paragraphs": [
            {
                "original": "古之學者必有師。師者，所以傳道、受業、解惑也。",
                "translation": "古代求學的人一定有老師。老師，是傳授道理、講授學業、解答疑惑的人。",
                "notes": "道：儒家之道。受：通「授」。闡明教師的三重職責。",
            },
            {
                "original": "是故無貴無賤，無長無少，道之所存，師之所存也。",
                "translation": "因此無論地位高低、年紀長少，道理所在之處，就是老師所在之處。",
                "notes": "強調擇師標準在「道」，不在貴賤長少。",
            },
        ],
    },
    {
        "id": "yue-yang-lou",
        "title": "岳陽樓記（節錄）",
        "author": "范仲淹",
        "source": "《范文正公集》",
        "dynasty": "北宋",
        "rhetoric": "駢散結合；寫景抒情，卒章顯志。",
        "exam_tips": "常考「不以物喜，不以己悲」與「先憂後樂」的抱負。",
        "paragraphs": [
            {
                "original": "嗟夫！予嘗求古仁人之心，或異二者之為，何哉？不以物喜，不以己悲。",
                "translation": "唉！我曾經探求古代仁人的心境，或許不同於上述兩種表現，為什麼呢？他們不因外物而喜，不因自己而悲。",
                "notes": "二者：指遷客騷人登樓時或喜或悲的兩種反應。",
            },
            {
                "original": "居廟堂之高，則憂其民；處江湖之遠，則憂其君。",
                "translation": "身居朝廷高位，就為百姓憂慮；身處江湖邊遠，就為君王憂慮。",
                "notes": "廟堂：朝廷。江湖：民間／貶謫之地。",
            },
            {
                "original": "先天下之憂而憂，後天下之樂而樂。",
                "translation": "在天下人憂慮之前先憂慮，在天下人快樂之後才快樂。",
                "notes": "全篇主旨所在，表現博大胸懷。",
            },
        ],
    },
]


def list_classical_texts() -> list[dict]:
    """Return the curated classical text set (public-domain originals)."""
    return CLASSICAL_TEXTS

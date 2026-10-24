import re



QUIZ = [
    ("MATEMATIKA", "Sebuah persegi panjang memiliki panjang 12 cm dan lebar 7 cm. Berapa kelilingnya?",
     "38 cm", ["38", "38 cm", "38 sentimeter", "tiga puluh delapan", "tiga puluh delapan cm"], [],
     "Keliling persegi panjang = 2 × (panjang + lebar)"),
    ("IPA", "Organ tubuh manusia yang berfungsi memompa darah ke seluruh tubuh adalah apa?",
     "Jantung", ["jantung", "organ jantung", "si jantung"], [("jantung",)],
     "Organ ini berada di rongga dada dan berdenyut terus-menerus sepanjang hidup kita."),
    ("IPS", "Kegiatan manusia untuk menghasilkan barang atau jasa guna memenuhi kebutuhan hidup disebut apa?",
     "Produksi", ["produksi", "kegiatan produksi", "memproduksi"], [("produksi",)],
     "Contohnya petani menanam padi dan pengrajin membuat kerajinan tangan."),
    ("BAHASA INDONESIA", "Dalam sebuah cerita, tokoh yang menentang tokoh utama disebut apa?",
     "Antagonis", ["antagonis", "tokoh antagonis", "peran antagonis"], [("antagonis",)],
     "Tokoh protagonis biasanya menjadi tokoh utama, sedangkan antagonis menjadi pihak yang menentangnya."),
    ("PPKN", "Apa cara terbaik untuk mengambil keputusan bersama sesuai sila keempat Pancasila?",
     "Musyawarah", ["musyawarah", "musyawarah mufakat", "bermusyawarah", "musyawarah untuk mufakat"], [("musyawarah",)],
     "Hargai pendapat orang lain dan utamakan kepentingan bersama."),
]


def normalize(s):
    s = str(s).lower()
    s = re.sub(r"[^a-z0-9\s]", " ", s)
    return re.sub(r"\s+", " ", s).strip()


def get(idx):
    return QUIZ[idx % len(QUIZ)]


def check(idx, answer):
    n = normalize(answer)
    if not n:
        return False
    if n in {normalize(a) for a in get(idx)[3]}:
        return True
    return any(all(k in n for k in rule) for rule in get(idx)[4])


def tip(idx):
    return "Tips: " + get(idx)[5]


def hint(idx):
    ans = get(idx)[2]
    return f"Petunjuk: diawali huruf \"{ans[0].upper()}\", {len(ans.replace(' ', ''))} karakter"

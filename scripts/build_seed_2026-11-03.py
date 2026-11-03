"""How data/sanctions.csv was built on 2026-11-03 (kept for provenance).

Every row was chosen by a person reading the candidate line; this script only formats the
chosen rows and asserts that each quote appears verbatim at its permalink.
Usage: python scripts/build_seed_2026-11-03.py candidates.tsv
"""
import csv, re, sys, urllib.parse
from pathlib import Path
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from wtl.fetch.mediawiki import page_wikitext
CAND = sys.argv[1]
rows = list(csv.reader(open(CAND), delimiter="\t"))[1:]

# (candidate index, username, type, duration, authority, notes)
AE = [
 (1,"Dan Palraz","topic_ban","6 months","AE",""),
 (3,"Salandarianflag","topic_ban","indefinite","AE",""),
 (5,"Tombah","topic_ban","indefinite","AE",""),
 (7,"בר","topic_ban","indefinite","AE",""),
 (9,"דוב","topic_ban","1 year","AE",""),
 (12,"Infinity Knight","topic_ban","indefinite","AE",""),
 (14,"Dan Palraz","topic_ban","indefinite","AE","second topic ban, after the 6-month one"),
 (15,"Andrevan","topic_ban","90 days","AE","account later renamed; see AndreJustAndre rows"),
 (16,"Nableezy","topic_ban","90 days","AE","reduced to 30 days on appeal (same log)"),
 (18,"Dovidroth","topic_ban","90 days","AE",""),
 (19,"SPECIFICO","topic_ban","60 days","AE",""),
 (20,"Iennes","topic_ban","indefinite","AE",""),
 (22,"Kazemita1","topic_ban","not stated","admin (unblock condition)","condition of unblock"),
 (23,"Sakiv","topic_ban","6 months","AE",""),
 (24,"Irtapil","topic_ban","indefinite","AE",""),
 (27,"Drsmoo","topic_ban","1 year","AE",""),
 (30,"Salmoonlight","topic_ban","indefinite","AE",""),
 (31,"Bakbik1234","topic_ban","indefinite","AE",""),
 (32,"Kashmiri","topic_ban","about 1 week","AE","for a 1RR breach"),
 (33,"Baratiiman","topic_ban","indefinite","AE",""),
 (36,"Crampcomes","topic_ban","6 months","AE",""),
 (38,"Anonymous Observer1945","topic_ban","indefinite","AE",""),
 (39,"Ecrusized","topic_ban","indefinite","AE",""),
 (40,"Davidlofgren1996","topic_ban","indefinite","AE",""),
 (41,"JDiala","topic_ban","indefinite","AE",""),
 (42,"Monopoly31121993(2)","topic_ban","indefinite","AE",""),
 (43,"Peleio Aquiles","topic_ban","indefinite","AE",""),
 (44,"Onlineone22","topic_ban","6 months","AE",""),
 (45,"Onlineone22","sockpuppet","indefinite","admin","indefinitely blocked as a sock (same log)"),
 (46,"Gabetucker2","topic_ban","indefinite","AE",""),
 (47,"Uricoh","topic_ban","indefinite","AE",""),
 (49,"JoeJShmo","topic_ban","6 months and 1521 edits","AE",""),
 (51,"Tobyw87","topic_ban","indefinite","AE",""),
 (52,"Emdosis","topic_ban","indefinite","AE",""),
 (53,"Vegan416","topic_ban","indefinite","AE",""),
 (54,"Ecpiandy","topic_ban","indefinite","AE",""),
 (57,"Ytyerushalmi","topic_ban","indefinite","AE",""),
 (58,"Silvertide goldwaves","topic_ban","indefinite","AE",""),
 (59,"EnfantDeLaVille","topic_ban","90 days","AE",""),
 (61,"Nishidani","topic_ban","3 weeks","AE",""),
 (63,"Snowstormfigorion","topic_ban","6 months","AE",""),
 (64,"Techiya1925","topic_ban","6 months","AE","scope: post-1948 Arab-Israeli conflict"),
 (65,"מתיאל","topic_ban","indefinite","AE",""),
 (66,"IdanST","topic_ban","indefinite","AE",""),
 (69,"TheCuratingEditor","topic_ban","6 months","AE",""),
 (71,"Bhjbggoonnv","topic_ban","indefinite","AE",""),
 (73,"Mk8mlyb","topic_ban","indefinite","AE",""),
 (74,"JohnR1Roberts","topic_ban","indefinite","AE",""),
 (75,"Pyramids09","topic_ban","indefinite","AE",""),
 (76,"KronosAlight","topic_ban","not stated","AE",""),
 (78,"דברי.הימים","topic_ban","not stated","admin",""),
 (79,"Apndrew","topic_ban","until extended-confirmed","admin",""),
 (81,"The Mountain of Eden","topic_ban","not stated","AE",""),
 (82,"Johnadams11","topic_ban","indefinite","AE","appeal to ArbCom unsuccessful (same log)"),
 (86,"Mikewem","topic_ban","until extended-confirmed","AE",""),
 (89,"Liythbc8832","sockpuppet","indefinite","admin","sockpuppet account, indefinitely blocked (same log)"),
 (90,"Konnichiwa222","topic_ban","indefinite","AN",""),
 (93,"Human Right Wiki","topic_ban","indefinite","admin",""),
 (94,"Closetside","topic_ban","indefinite","admin",""),
 (96,"VoiceofTruthForTheVoiceless","topic_ban","1 year","admin",""),
 (97,"Mikewem","topic_ban","not stated","AE","second topic ban"),
 (99,"שמי (2023)","topic_ban","1 year","ANI",""),
 (100,"Crampcomes","topic_ban","not stated","admin","second topic ban"),
 (102,"Rafe87","topic_ban","not stated","admin","after balanced-editing-restriction violations"),
 (104,"Aesurias","topic_ban","not stated","AE",""),
 (106,"Easternsahara","topic_ban","not stated","AE",""),
 (111,"Coining","topic_ban","indefinite","admin",""),
 (114,"JJNito197","topic_ban","indefinite","AE",""),
 (116,"FarFromTheMiddleEast","topic_ban","indefinite","AE",""),
 (117,"TarnishedPath","topic_ban","90 days","admin",""),
 (118,"Wh1pla5h99","topic_ban","indefinite","admin",""),
 (119,"Arminden","topic_ban","indefinite","AE",""),
 (121,"Patrick.N.L","topic_ban","not stated","AE",""),
 (122,"NorthernWinds","topic_ban","not stated","AE",""),
 (125,"Slava570","topic_ban","not stated","AE",""),
 # Eastern Europe: bans covering the whole area or the Russia-Ukraine conflict
 (127,"Gitz6666","topic_ban","indefinite","ANI","scope: Russo-Ukrainian War"),
 (129,"Jargo Nautilus","topic_ban","indefinite","admin","scope: modern armed conflicts in Eastern Europe"),
 (137,"Osterluzei","topic_ban","until 2024-05-01","admin","scope: Russo-Ukrainian War"),
 (147,"Mzajac","topic_ban","indefinite","admin","scope: Ukraine-Russia conflict and place names"),
 (149,"Stanislawskachko","topic_ban","not stated","admin (unblock condition)","scope: Russia, Ukraine, Russo-Ukrainian War"),
 (153,"Mhorg","topic_ban","indefinite","AE","scope: Eastern Europe"),
 (154,"Walter Tau","topic_ban","indefinite","admin","scope: Russo-Ukrainian war"),
 (161,"Koqevar61","topic_ban","indefinite","admin","scope: Balkans or Eastern Europe"),
 (162,"TurboSuperA+","topic_ban","not stated","AE","scope: Russian and Ukrainian topics"),
 (164,"Buk21","sockpuppet","indefinite","admin","blocked for abusing multiple accounts (SPI)"),
 # South Asia (India-Pakistan-Afghanistan): bans covering India and/or Pakistan broadly
 (165,"PreserveOurHistory","topic_ban","indefinite","AE",""),
 (167,"Pbeditwiki","topic_ban","1 month","admin","scope: India"),
 (169,"Karsan Chanda","topic_ban","indefinite","admin",""),
 (173,"Rahil1610","topic_ban","until 2023-08-31","admin","scope: India"),
 (175,"1Firang","topic_ban","indefinite","admin",""),
 (178,"Starkex","topic_ban","indefinite","admin",""),
 (185,"Anubhavklal","topic_ban","indefinite","admin",""),
 (186,"Thewikiuser1999","topic_ban","indefinite","admin",""),
 (190,"Makks2010","topic_ban","indefinite","admin",""),
 (192,"Afv12e","topic_ban","indefinite","AE",""),
 (194,"BlackOrchidd","topic_ban","indefinite","AE",""),
 (198,"TuberGotTubed","topic_ban","indefinite","admin",""),
 (201,"Jonharojjashi","topic_ban","indefinite","admin",""),
 (202,"Thewikizoomer","topic_ban","indefinite","ANI",""),
 (203,"ThatBritishAsianDude","topic_ban","indefinite","AE",""),
 (204,"JingJongPascal","topic_ban","indefinite","admin",""),
 (205,"Loveforwiki","topic_ban","indefinite","AE",""),
 (206,"Southasianhistorian8","topic_ban","6 months and 500 edits","AE",""),
 (207,"Rasteem","topic_ban","6 months and 500 edits","AE","scope: India and Pakistan"),
 (211,"Dympies","topic_ban","indefinite","admin",""),
 (212,"PadFoot2008","topic_ban","not stated","AE",""),
 (213,"Maniacal ! Paradoxical","topic_ban","not stated","AE",""),
 (214,"TPGOK","topic_ban","1 year","admin",""),
 (224,"TheInspectorInCity","topic_ban","1 month","admin","scope: Pakistan-India conflicts and Indian military events"),
]

SIGCUT = re.compile(r"\s*(<sub>signed|\[\[User:|\[\[user:|<span|<b>\s*\[\[|—&nbsp;|--\s*\[\[|-- \[\[|~ Jenson|<small class=\"autosigned\"|<!--)")
def quote_of(line):
    q = line.lstrip("*:# ")
    m = SIGCUT.search(q)
    if m: q = q[:m.start()]
    q = q.rstrip(" .-")
    if len(q) > 240:
        q = q[:240].rsplit(" ", 1)[0]
    return q

def rendered(q):
    t = re.sub(r"\{\{\s*(?:user|userlinks|noping2?|no ping|np2?|u|checkuser)\s*\|\s*([^|}]+)\}\}", r"\1", q, flags=re.I)
    t = re.sub(r"\[\[(?:[^|\]]*\|)?([^\]]*)\]\]", r"\1", t)
    t = re.sub(r"\[https?://\S+ ([^\]]*)\]", r"\1", t)
    t = re.sub(r"\{\{[^}]*\}\}|<[^>]+>|'''?|\[https?://\S+\]", "", t)
    return " ".join(t.split())

def frag(q):
    words = rendered(q).split()[:6]
    return "#:~:text=" + urllib.parse.quote(" ".join(words), safe="").replace("-", "%2D")

out = []
pages = {}
def page(revid):
    if revid not in pages: pages[revid] = page_wikitext(revid)
    return pages[revid]

for idx, user, typ, dur, auth, notes in AE:
    area, revid, title, users, date, line = rows[idx-1]
    assert user in users.split(";") or user in line, (idx, user, users)
    assert date, (idx, user)
    q = quote_of(line)
    w = page(int(revid))["wikitext"]
    assert q in w, (idx, q)
    url = f"https://en.wikipedia.org/w/index.php?title={urllib.parse.quote(title.replace(' ','_'))}&oldid={revid}{frag(q)}"
    out.append([user, typ, area, dur, date, auth, url, q, notes])

# Arbitration Committee decisions (quotes copied from the pages; checked below)
PIA5 = 1334391260; ACN14 = 1323595679; ACN15 = 1383057886
def arb(user, typ, dur, date, revid, title, anchor, quote, notes=""):
    w = page(revid)["wikitext"]
    assert quote in w, (user, quote)
    url = f"https://en.wikipedia.org/w/index.php?title={urllib.parse.quote(title.replace(' ','_'))}&oldid={revid}#{urllib.parse.quote(anchor.replace(' ','_'))}"
    out.append([user, typ, "A-I", dur, date, "ArbCom", url, quote, notes])

T5 = "Wikipedia:Arbitration/Requests/Case/Palestine-Israel_articles_5"
for u in ["BilledMammal","Iskandar323","Levivich","Nableezy","Selfstudier","Makeandtoss","Nishidani"]:
    arb(u,"topic_ban","indefinite","2025-01-23",PIA5,T5,f"{u} indefinite topic ban",
        f"{u} is indefinitely topic banned from the Palestine-Israel conflict, broadly construed.")
arb("AndreJustAndre","topic_ban","indefinite","2025-01-23",PIA5,T5,"AndreJustAndre indefinite topic ban",
    "AndreJustAndre is indefinitely topic banned from the Palestine-Israel conflict, broadly construed.")
arb("האופה","sockpuppet","indefinite","2025-01-23",PIA5,T5,"האופה blocked",
    "{{User|האופה}} was blocked during this case as a sockpuppet of {{noping|Galamore}}.",
    "date is when the finding passed; the block itself was earlier, during the case")
T14 = "Wikipedia:Arbitration_Committee/Noticeboard/Archive_14"
A1 = "Arbitration motion regarding PIA Canvassing"
arb("Dovidroth","site_ban","indefinite","2024-01-20",ACN14,T14,A1,
    "the Committee determines that {{User|Dovidroth}} most likely participated in discussions due to canvassing and made proxy edits for a banned editor. As a result, they are indefinitely banned from Wikipedia.")
arb("Dovidroth","topic_ban","indefinite","2024-01-20",ACN14,T14,A1,
    "the Committee determines that {{User|Dovidroth}} most likely made proxy edits for a banned editor. As a result, they are indefinitely [[Wikipedia:Banning policy#Topic ban|topic banned]]")
arb("EytanMelech","site_ban","indefinite","2024-01-20",ACN14,T14,A1,
    "the Committee determines that {{User|EytanMelech}} most likely made proxy edits for a banned editor. As a result, he is indefinitely banned from Wikipedia.",
    "site ban lifted on appeal 2024-09-01; topic ban remains (same archive, 'EytanMelech unbanned')")
arb("EytanMelech","topic_ban","indefinite","2024-01-20",ACN14,T14,A1,
    "the Committee determines that {{User|EytanMelech}} most likely made proxy edits for a banned editor. As a result, they are indefinitely [[Wikipedia:Banning policy#Topic ban|topic banned]]")
arb("Homerethegreat","topic_ban","indefinite","2024-01-20",ACN14,T14,A1,
    "the Committee determines that {{User|Homerethegreat}} most likely participated in discussions due to canvassing and made proxy edits for a banned editor. As a result, they are indefinitely [[Wikipedia:Banning policy#Topic ban|topic banned]]")
A2 = "Off-wiki misconduct in Palestine–Israel topic area"
arb("Ïvana","site_ban","indefinite","2024-12-09",ACN14,T14,A2,
    "{{Userlinks|Ïvana}} is indefinitely banned from Wikipedia.")
arb("Ïvana","topic_ban","indefinite","2024-12-09",ACN14,T14,A2,
    "{{Userlinks|Ïvana}} is topic banned from the [[WP:PIA|Palestine–Israel topic area]], broadly construed.")
arb("Samisawtak","topic_ban","indefinite","2024-12-09",ACN14,T14,A2,
    "{{user|Samisawtak}} is topic banned from the Palestine–Israel topic area, broadly construed.")
A3 = "Off-wiki misconduct in Palestine–Israel topic area II"
arb("Isoceles-sai","site_ban","indefinite","2025-04-26",ACN14,T14,A3,
    "{{user|Isoceles-sai}} is banned from the English Wikipedia.")
arb("GeoColdWater","site_ban","indefinite","2025-04-26",ACN14,T14,A3,
    "{{user|GeoColdWater}} is banned from the English Wikipedia.")
arb("Someonefighter","topic_ban","indefinite","2025-05-09",ACN14,T14,"Someonefighter",
    "{{user|Someonefighter}}'s [[Special:Diff/1288399891|site ban]] is vacated and replaced with an indefinite topic ban from the Arab-Israeli conflict (broadly construed).",
    "replaces a site ban of 2025-05-02, vacated on appeal")
arb("Iskandar323","site_ban","indefinite","2026-01-23",ACN15,"Wikipedia:Arbitration_Committee/Noticeboard/Archive_15",
    "Arbitration motions regarding ARBPIA5 topic bans",
    "Iskandar323 is indefinitely banned from the English Wikipedia.")

out.sort(key=lambda r: (r[2], r[4], r[0].lower(), r[1]))
dst = ROOT / "data" / "sanctions.csv"
with open(dst, "w", newline="", encoding="utf-8") as f:
    wr = csv.writer(f)
    wr.writerow(["username","sanction_type","area","duration","date","authority","decision_url","source_quote","notes"])
    wr.writerows(out)
from collections import Counter
print(len(out), Counter((r[2], r[1]) for r in out))

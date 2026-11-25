#!/usr/bin/env python3
import csv
import re
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OVERRIDES = ROOT / "lists" / "label_overrides.csv"
OVERRIDE_FIELDS = ["label", "canonical", "category", "updated"]

ALIASES = {
    "wise man": "wise man", "magus": "wise man", "magi": "wise man", "king": "wise man", "three kings": "wise man",
    "christ child": "Christ Child", "infant christ": "Christ Child", "christ": "Christ Child", "baby jesus": "Christ Child",
    "mary": "Mary", "virgin mary": "Mary", "madonna": "Mary", "virgin": "Mary", "joseph": "Joseph", "saint joseph": "Joseph",
    "star of bethlehem": "Star of Bethlehem",
    "fir tree": "conifer", "pine tree": "conifer", "pine": "conifer", "fir": "conifer", "spruce": "conifer", "umbrella pine tree": "conifer",
    "pitcher": "jug", "ewer": "jug", "cream jug": "jug",
    "cookie": "biscuits", "cookies": "biscuits", "biscuit": "biscuits",
    "rooster": "chicken", "cockerel": "chicken", "hen": "chicken",
    "figure": "person", "figures": "crowd", "people": "crowd", "group": "crowd", "group of people": "crowd", "crowd of people": "crowd",
    "snow on ground": "snow", "snow-covered ground": "snow", "snowy landscape": "snow", "snowy ground": "snow",
    "row boat": "boat", "rowing boat": "boat", "sailing boat": "boat", "rowboat": "boat",
    "tea cup": "cup", "teacup": "cup", "wine goblet": "goblet",
    "bunch of grapes": "grapes", "grape": "grapes",
    "glass of water": "glass", "drinking glass": "glass", "tumbler": "glass",
    "framed painting": "framed picture", "painting": "framed picture", "picture": "framed picture",
    "spaniel": "dog", "spaniel dog": "dog", "poodle": "dog", "greyhound": "dog", "sailboat": "boat", "piglet": "pig",
    "hay stack": "haystack", "hay bale": "haystack", "lamp post": "street lamp", "picture frame": "framed picture",
    "angel group": "angel", "tree group": "tree", "tree branch": "branch", "leafy branch": "branch", "pine branch": "branch",
    "evergreen sprig": "branch", "wagon wheel": "wheel", "cart wheel": "wheel", "couple": "crowd", "couple walking": "crowd",
    "gifts of the magi": "gifts of the Magi", "gift of the magi": "gifts of the Magi", "frozen stream": "frozen river",
    "castle ruin": "castle", "rocky cliff": "rock", "rock formation": "rock", "rocky slope": "hill", "hillside": "hill",
    "snowfall": "snow", "jewellery": "jewellery", "creamer": "jug", "lampshade": "lamp", "paintbrush": "brush", "tomatoe": "tomato", "potatoe": "potato",
}
KEEP_COMPOUNDS = {
    "christmas tree", "palm tree", "orange tree", "wine glass", "wine bottle", "toy boat", "gift box", "torii gate",
    "music book", "viola da gamba", "framed picture", "Christ Child", "Star of Bethlehem", "wise man", "ice skates",
    "top hat", "paper lantern", "stone lantern", "leg of mutton", "bread roll", "lemon slices", "candlestick",
}
PLURAL_NOUNS = {"grapes", "nuts", "biscuits", "icicles", "chestnuts", "clothes", "lemon slices", "olives", "ice skates",
                "mussels", "scissors", "glasses", "spectacles", "sweets", "dates", "raisins", "almonds", "walnuts", "hazelnuts"}
PEOPLE = r"(?:man|woman|girl|boy|child|person|baby|lady|gentleman|figure|old man|old woman|young woman|young man|wise man|magus|soldier|servant|shepherd|skater|musician|monk|nun|priest|rider|traveller|vendor|samurai|courtesan|actor|dancer|people|group of people|group of children|group of adults|children|women|men)"
MODIFIERS = {
    "black", "white", "red", "blue", "green", "yellow", "brown", "grey", "gray", "pink", "purple", "golden", "dark", "light",
    "pale", "bright", "wooden", "woven", "wicker", "earthenware", "copper", "metal", "pewter", "silver", "gold", "gilt",
    "porcelain", "brass", "iron", "ceramic", "clay", "stone", "straw", "small", "large", "tall", "big", "little", "tiny", "huge",
    "bare", "sleeping", "decorated", "broken", "patterned", "striped", "checkered", "upholstered", "folding", "crumpled",
    "stacked", "snow-covered", "snowy", "thatched", "winter", "lit", "burning", "open", "closed", "half", "peeled", "sliced",
    "ornate", "carved", "painted", "floral", "fur-trimmed", "feathered", "conical", "arched", "picket", "standing", "sitting",
    "seated", "kneeling", "walking", "flying", "running", "lying", "distant", "single", "round", "square", "empty", "full",
}
COLOURISH = re.compile(r"^(?:(?:%s)(?:\s+and\s+|\s*,\s*|\s+))+" % "|".join(sorted(MODIFIERS, key=len, reverse=True)))
CONTAINERS_OF = {"basket", "bowl", "plate", "dish", "tray", "jar", "box", "bag", "pile", "heap", "stack", "branch", "sprig", "vase"}
QUANTITY_OF = {"bunch", "cluster", "slice", "slices", "piece", "pieces", "pair", "handful", "string", "row", "field"}

CATEGORIES = {
    "people": "couple clown man woman girl boy child person baby lady figure crowd soldier servant shepherd skater musician monk nun priest rider traveller vendor samurai courtesan actor dancer guard king queen hunter farmer woodcutter fisherman sailor beggar",
    "holy figures": "Christ Child|Mary|Joseph|angel|wise man|saint|halo|Star of Bethlehem|cherub|God|Holy Spirit|manger|censer|gifts of the Magi|glass orb",
    "animals": "dog cat horse sheep ox donkey cow goat monkey puppy fox bear deer rabbit hare pig lamb camel mule squirrel mouse lion elephant bull calf kitten creature frog spider butterfly goldfish pig",
    "birds": "bird chicken sparrow duck goose swan peacock dove robin crow crane parrot owl pigeon heron magpie pheasant partridge chick bird's nest hanging birdcage",
    "fruit": "apple pear plum cherry peach orange lemon grapes fig strawberry melon pomegranate berry apricot quince raspberry blackberry currant banana pineapple lime citrus fruit watermelon persimmon coconut tomato pumpkin slice",
    "food and drink": "pie bread cheese nuts biscuits cake oyster fish meat egg ham bread roll sweets chestnuts walnut hazelnut almond olives mussels lobster crab shrimp sausage butter honey leg of mutton pumpkin asparagus vegetable cabbage artichoke onion mushroom game wine pudding dessert lemon slices dates raisins sugar pepper carrot aubergine pea pod food sugar cube sugar skull dried herb wheat sheaf",
    "tableware": "jug glass wine glass bottle wine bottle cup plate bowl knife spoon fork tablecloth teapot tray dish goblet salt cellar jar vase basket pot pan kettle napkin cutlery tumbler flask carafe decanter platter container vessel saucer tankard creamer fishbowl urn sugar tong paper cone mortar and pestle",
    "light": "candle candlestick lantern paper lantern stone lantern lamp fire torch fireplace chandelier street lamp lamp post lamp lampshade match incense burner",
    "plants": "flower plant holly ivy leaf leaves mistletoe camellia plum blossom daffodil rose tulip iris lily bamboo grass reed vine wreath garland pinecone blossom bouquet peony chrysanthemum fern branch thistle hollyhock agave vine tendril rose bush reeds bushe bush plum blossom pine branch",
    "trees": "tree conifer palm tree christmas tree orange tree willow birch oak",
    "winter": "snow icicles snowball snowman snowflake ice skates sledge sleigh frozen river ice ice block frozen river frozen stream snowfall icicle",
    "buildings": "building house temple church bridge gate torii gate roof castle tower fence wall window door shrine pagoda cottage cabin hut barn tent arch archway column staircase veranda balcony street well stable pillar shutter chimney pulpit village town watermill fountain scaffolding doorway railing balustrade pergola shed lectern throne covered walkway architectural structure castle ruin notre dame telegraph pole fence post floor tile beam ceiling floor ledge post",
    "transport": "boat toy boat cart carriage ship wagon wheelbarrow palanquin raft sailboat stagecoach sleigh emblem cart wheel wagon wheel wheel saddle steam locomotive railway signal",
    "clothing": "hat top hat umbrella parasol kimono coat dress scarf shoe boot cloak robe glove mittens crown fan veil headdress shawl apron bag purse helmet sandal necklace sash headscarf armband handbag earring hairpin slipper jewellery pouch bodice bonnet cap brooch stocking hair bow pearl necklace fur stole powder puff",
    "music": "lute violin viola da gamba recorder drum music book flute guitar harp trumpet horn bell piano organ shamisen koto musical instrument violin case instrument case music sheet",
    "toys and games": "toy doll ball kite battledore shuttlecock present gift box hobby horse spinning top game cards dice croquet hoop croquet mallet board",
    "landscape": "mountain hill river sky cloud moon sun rock lake sea field forest waterfall island path road mountain peak landscape water hillside riverbank ground rocky slope rock formation rocky cliff star snowfall steam haystack hay stack",
    "things": "book framed picture mirror letter envelope note postcard ticket photograph clock chair table bed stool bench cabinet chest box cushion pillow blanket rug curtain screen towel clothes broom bucket ladder pipe sword spear flag scroll brush stamp ribbon coin key banner staff statue laundry stick cloth bust drawing sack canvas barrel coffin whip telescope drapery chain shelf crate easel bundle sign stand shelter rope border scene object crook cradle pitchfork paper poster axe stack sawhorse log paintbrush carpet bedding signpost divan armchair spinning wheel knitting needle watering can framed map wall hanging animal skull decorative border hanging decoration laundry bundle fishing rod picture frame nose firewood beam",
}
CATEGORY_OF = {}
for cat, words in CATEGORIES.items():
    if "|" in words:
        CATEGORY_OF.update({w.strip(): cat for w in words.split("|")})
MULTI = {"bread roll", "leg of mutton", "lemon slices", "wine glass", "wine bottle", "salt cellar", "paper lantern", "stone lantern",
         "plum blossom", "palm tree", "christmas tree", "orange tree", "ice skates", "frozen river", "torii gate", "toy boat", "top hat",
         "viola da gamba", "music book", "gift box", "hobby horse", "spinning top", "framed picture", "mountain peak",
         "bird's nest", "hanging birdcage", "pumpkin slice", "pea pod", "sugar cube", "sugar skull", "dried herb", "wheat sheaf",
         "sugar tong", "paper cone", "mortar and pestle", "street lamp", "lamp post", "incense burner", "vine tendril", "rose bush",
         "plum blossom", "pine branch", "ice block", "frozen stream", "covered walkway", "architectural structure", "castle ruin",
         "notre dame", "telegraph pole", "fence post", "floor tile", "beam ceiling", "sleigh emblem", "cart wheel", "wagon wheel",
         "steam locomotive", "railway signal", "hair bow", "pearl necklace", "fur stole", "powder puff", "musical instrument",
         "violin case", "instrument case", "music sheet", "croquet hoop", "croquet mallet", "rocky slope", "rock formation",
         "rocky cliff", "hay stack", "spinning wheel", "knitting needle", "watering can", "framed map", "wall hanging",
         "animal skull", "decorative border", "hanging decoration", "laundry bundle", "fishing rod", "picture frame", "glass orb"}
for cat, words in CATEGORIES.items():
    if "|" in words:
        continue
    rest = words
    for m in sorted(MULTI, key=len, reverse=True):
        if re.search(rf"\b{re.escape(m)}\b", rest):
            CATEGORY_OF[m] = cat
            rest = re.sub(rf"\b{re.escape(m)}\b", " ", rest)
    for w in rest.split():
        CATEGORY_OF.setdefault(w, cat)


def singular(word):
    if word in PLURAL_NOUNS:
        return word
    for end, rep in (("ies", "y"), ("ches", "ch"), ("shes", "sh"), ("xes", "x"), ("sses", "ss"), ("ves", "f")):
        if word.endswith(end) and len(word) >= len(end) + 2:
            return word[: -len(end)] + rep
    if word.endswith("s") and not word.endswith(("ss", "us", "is", "as")) and len(word) > 3:
        return word[:-1]
    return word


def canonical(label):
    raw = label.strip()
    low = re.sub(r"\s+", " ", raw.lower())
    low = re.sub(r"\s*\((?:in )?(?:the )?background\)|\s+in (?:the )?background|\s+in (?:the )?distance", "", low).strip()
    if low in ALIASES:
        return ALIASES[low]
    m = re.match(rf"^{PEOPLE}\b(?:\s+(?:in|with|holding|carrying|wearing|on|at|near|by|under|sitting|standing|lying|kneeling|walking|playing|reading|riding|pulling|pushing|drinking|eating|looking|leaning|dancing|knitting|behind|beside|running|skating|singing|working|fishing)\b.*)?$", low)
    if m:
        head = re.match(rf"^{PEOPLE}", low).group(0)
        if head in ("people", "group of people", "group of children", "group of adults", "children", "women", "men"):
            return "crowd"
        return ALIASES.get(head, singular(head) if head not in ("old man", "old woman", "young woman", "young man") else head.split()[-1])
    if low.startswith("group of ") or low.startswith("crowd of "):
        return "crowd"
    m = re.match(r"^(\w+) of (.+)$", low)
    if m and m.group(1) in QUANTITY_OF:
        return canonical(m.group(2))
    if m and m.group(1) in CONTAINERS_OF:
        low = m.group(1)
    low = re.sub(r"^(?:snow-covered|snowy)\s+", "", low)
    if low in ALIASES:
        return ALIASES[low]
    if low not in {k.lower() for k in KEEP_COMPOUNDS}:
        stripped = COLOURISH.sub("", low).strip()
        if stripped:
            low = stripped
    low = re.sub(r"\s+(?:with|on|in|near|under|by|behind|beside)\s+.*$", "", low) if low not in {k.lower() for k in KEEP_COMPOUNDS} else low
    if low in ALIASES:
        return ALIASES[low]
    words = low.split()
    if low not in {k.lower() for k in KEEP_COMPOUNDS} and words:
        words[-1] = singular(words[-1])
        low = " ".join(words)
    if len(words) >= 2 and words[-1] == "tree" and low not in KEEP_COMPOUNDS:
        low = "tree"
    if low in ALIASES:
        return ALIASES[low]
    for k in KEEP_COMPOUNDS:
        if k.lower() == low:
            return k
    return low


def category(canon):
    if canon in CATEGORY_OF:
        return CATEGORY_OF[canon]
    last = canon.split()[-1] if canon else ""
    return CATEGORY_OF.get(last, CATEGORY_OF.get(singular(last), ""))


def read_overrides():
    if not OVERRIDES.exists():
        return {}
    with open(OVERRIDES, newline="", encoding="utf-8") as f:
        return {r["label"]: r for r in csv.DictReader(f)}


def resolve(label, overrides=None):
    overrides = read_overrides() if overrides is None else overrides
    key = label.strip().lower()
    o = overrides.get(key, {})
    canon = o.get("canonical") or canonical(label)
    cat_override = overrides.get("=" + canon, {}).get("category")
    return {"label": key, "canonical": canon, "rule_canonical": canonical(label),
            "category": o.get("category") or cat_override or category(canon), "rule_category": category(canon)}


if __name__ == "__main__":
    labels = Counter()
    with open(ROOT / "runs" / "detect_items.csv", newline="", encoding="utf-8") as f:
        for r in csv.DictReader(f):
            labels[r["label"].strip().lower()] += 1
    groups = Counter()
    for label, n in labels.items():
        groups[canonical(label)] += n
    print(f"{len(labels)} labels -> {len(groups)} canonical, {sum(1 for g in groups if not category(g))} without category")
    if "-v" in sys.argv:
        for g, n in groups.most_common():
            print(f"{n:4} {g:30} {category(g)}")

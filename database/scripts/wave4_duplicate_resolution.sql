-- =============================================================================
-- WAVE 4: DUPLICATE CAPTION RESOLUTION SCRIPT
-- Generated: 2025-12-15
-- Purpose: Resolve 117 duplicate caption pairs with inconsistent classifications
-- Method: wave4_duplicate_resolver
-- Confidence: 0.85
-- =============================================================================
-- Resolution Rules Applied:
-- 1. When one has content_type_id and one is NULL -> use the non-NULL value
-- 2. When both have content_type_id but different -> analyze caption text for accuracy
-- 3. When caption_types differ -> prefer more specific type (dm_farm > bump_normal)
-- 4. Priority order: explicit > implied > teasing (for content hints)
-- 5. Higher performance_score preferred when ambiguous (all are 50.0 here)
-- =============================================================================

BEGIN TRANSACTION;

-- -----------------------------------------------------------------------------
-- GROUP 1: NULL content_type_id Resolution (propagate non-NULL to NULL record)
-- These are straightforward: one record has content_type_id, the other is NULL
-- -----------------------------------------------------------------------------

-- Pair 19662/60890: "Something red for when you're off work" - flash_sale(27) promotional
UPDATE caption_bank SET content_type_id = 27, classification_confidence = 0.85, classification_method = 'wave4_duplicate_resolver' WHERE caption_id = 60890;

-- Pair 19663/60891: "The football season is back on" - teasing(31)
UPDATE caption_bank SET content_type_id = 31, classification_confidence = 0.85, classification_method = 'wave4_duplicate_resolver' WHERE caption_id = 60891;

-- Pair 19664/60892: "What are you doing this evening hun?" - teasing(31)
UPDATE caption_bank SET content_type_id = 31, classification_confidence = 0.85, classification_method = 'wave4_duplicate_resolver' WHERE caption_id = 60892;

-- Pair 19665/60893: "It's always nice to see you hun" - teasing(31)
UPDATE caption_bank SET content_type_id = 31, classification_confidence = 0.85, classification_method = 'wave4_duplicate_resolver' WHERE caption_id = 60893;

-- Pair 19666/60894: "I'm ready to do some work now" - teasing(31)
UPDATE caption_bank SET content_type_id = 31, classification_confidence = 0.85, classification_method = 'wave4_duplicate_resolver' WHERE caption_id = 60894;

-- Pair 19670/61267: "Your favourite distraction just walked in" - teasing(31)
UPDATE caption_bank SET content_type_id = 31, classification_confidence = 0.85, classification_method = 'wave4_duplicate_resolver' WHERE caption_id = 61267;

-- Pair 19673/61270: "Built to break hearts and a few rules" - teasing(31)
UPDATE caption_bank SET content_type_id = 31, classification_confidence = 0.85, classification_method = 'wave4_duplicate_resolver' WHERE caption_id = 61270;

-- Pair 19713/61235: "LIKE and i'll take it off" - flash_sale(27) promotional
UPDATE caption_bank SET content_type_id = 27, classification_confidence = 0.85, classification_method = 'wave4_duplicate_resolver' WHERE caption_id = 61235;

-- Pair 19729/61002: "Feeling kinda sweet but also kinda sinful" - teasing(31)
UPDATE caption_bank SET content_type_id = 31, classification_confidence = 0.85, classification_method = 'wave4_duplicate_resolver' WHERE caption_id = 61002;

-- Pair 19730/61003: "If you were here, would you make me smile or make me moan?" - teasing(31)
-- Also: caption_type differs (bump_normal vs dm_farm). Question-based = dm_farm is more accurate
UPDATE caption_bank SET content_type_id = 31, caption_type = 'dm_farm', classification_confidence = 0.85, classification_method = 'wave4_duplicate_resolver' WHERE caption_id = 19730;
UPDATE caption_bank SET content_type_id = 31, caption_type = 'dm_farm', classification_confidence = 0.85, classification_method = 'wave4_duplicate_resolver' WHERE caption_id = 61003;

-- Pair 19732/61005: "figured this looks cool, what do u think?" - teasing(31)
UPDATE caption_bank SET content_type_id = 31, classification_confidence = 0.85, classification_method = 'wave4_duplicate_resolver' WHERE caption_id = 61005;

-- Pair 19733/61006: "I look innocent, but I'd ruin your focus" - teasing(31)
UPDATE caption_bank SET content_type_id = 31, classification_confidence = 0.85, classification_method = 'wave4_duplicate_resolver' WHERE caption_id = 61006;

-- Pair 19734/61007: "Just a sweet girl doing not-so-sweet things" - teasing(31)
UPDATE caption_bank SET content_type_id = 31, classification_confidence = 0.85, classification_method = 'wave4_duplicate_resolver' WHERE caption_id = 61007;

-- Pair 19735/61008: "Is this the kind of photo that would make you smile or bite your lip?" - teasing(31)
UPDATE caption_bank SET content_type_id = 31, classification_confidence = 0.85, classification_method = 'wave4_duplicate_resolver' WHERE caption_id = 61008;

-- Pair 19739/60935: "Thinking we could have a lot of fun on your floor!" - teasing(31)
UPDATE caption_bank SET content_type_id = 31, classification_confidence = 0.85, classification_method = 'wave4_duplicate_resolver' WHERE caption_id = 60935;

-- Pair 19740/60936: "They're all yours. I don't want you to hold it in any longer" - teasing(31)
UPDATE caption_bank SET content_type_id = 31, classification_confidence = 0.85, classification_method = 'wave4_duplicate_resolver' WHERE caption_id = 60936;

-- Pair 19742/60938: "Let me know if you're interested in a housekeeper" - teasing(31) already both dm_farm
UPDATE caption_bank SET content_type_id = 31, classification_confidence = 0.85, classification_method = 'wave4_duplicate_resolver' WHERE caption_id = 60938;

-- Pair 19743/60939: "Love squeezing them together while you're in between!" - teasing(31)
UPDATE caption_bank SET content_type_id = 31, classification_confidence = 0.85, classification_method = 'wave4_duplicate_resolver' WHERE caption_id = 60939;

-- Pair 19744/60940: "The moment before I'm covered" - teasing(31)
UPDATE caption_bank SET content_type_id = 31, classification_confidence = 0.85, classification_method = 'wave4_duplicate_resolver' WHERE caption_id = 60940;

-- Pair 19746/60885: "Are you glad to see me darling?" - teasing(31)
UPDATE caption_bank SET content_type_id = 31, classification_confidence = 0.85, classification_method = 'wave4_duplicate_resolver' WHERE caption_id = 60885;

-- Pair 19747/60886: "Join me tonight for a dinner in your honor" - joi(12)
UPDATE caption_bank SET content_type_id = 12, classification_confidence = 0.85, classification_method = 'wave4_duplicate_resolver' WHERE caption_id = 60886;

-- Pair 19750/60889: "When they say look in the mirror, you should listen" - teasing(31)
UPDATE caption_bank SET content_type_id = 31, classification_confidence = 0.85, classification_method = 'wave4_duplicate_resolver' WHERE caption_id = 60889;

-- Pair 19755/60895: "are u thinking of me right now??" - teasing(31)
UPDATE caption_bank SET content_type_id = 31, classification_confidence = 0.85, classification_method = 'wave4_duplicate_resolver' WHERE caption_id = 60895;

-- Pair 19757/60897: "I'll be a good pet" - teasing(31)
UPDATE caption_bank SET content_type_id = 31, classification_confidence = 0.85, classification_method = 'wave4_duplicate_resolver' WHERE caption_id = 60897;

-- Pair 19758/60898: "would you give it a spank?" - teasing(31)
-- Also: caption_type differs. Question = dm_farm is more accurate
UPDATE caption_bank SET content_type_id = 31, caption_type = 'dm_farm', classification_confidence = 0.85, classification_method = 'wave4_duplicate_resolver' WHERE caption_id = 19758;
UPDATE caption_bank SET content_type_id = 31, caption_type = 'dm_farm', classification_confidence = 0.85, classification_method = 'wave4_duplicate_resolver' WHERE caption_id = 60898;

-- Pair 19759/60899: "Welcome to my pageee" - teasing(31)
UPDATE caption_bank SET content_type_id = 31, classification_confidence = 0.85, classification_method = 'wave4_duplicate_resolver' WHERE caption_id = 60899;

-- Pair 19762/60919: "I won't show everything...but I'll show just enough" - teasing(31) already both dm_farm
UPDATE caption_bank SET content_type_id = 31, classification_confidence = 0.85, classification_method = 'wave4_duplicate_resolver' WHERE caption_id = 60919;

-- Pair 19763/60920: "There's something about soft outfits and tight shorts" - teasing(31)
-- caption_type differs: bump_descriptive vs dm_farm. "What do you think?" = dm_farm is more specific
UPDATE caption_bank SET content_type_id = 31, caption_type = 'dm_farm', classification_confidence = 0.85, classification_method = 'wave4_duplicate_resolver' WHERE caption_id = 19763;
UPDATE caption_bank SET content_type_id = 31, caption_type = 'dm_farm', classification_confidence = 0.85, classification_method = 'wave4_duplicate_resolver' WHERE caption_id = 60920;

-- Pair 19764/60921: "is it normal for butterflies to turn into fireworks after dark?" - implied_solo(35)
UPDATE caption_bank SET content_type_id = 35, classification_confidence = 0.85, classification_method = 'wave4_duplicate_resolver' WHERE caption_id = 60921;

-- Pair 19766/60923: "Do I look sweet enough to fool you" - teasing(31)
UPDATE caption_bank SET content_type_id = 31, classification_confidence = 0.85, classification_method = 'wave4_duplicate_resolver' WHERE caption_id = 60923;

-- Pair 19767/60924: "Tell me honestly...is it the wig, the straps, or the bed" - teasing(31) already both dm_farm
UPDATE caption_bank SET content_type_id = 31, classification_confidence = 0.85, classification_method = 'wave4_duplicate_resolver' WHERE caption_id = 60924;

-- Pair 19768/60925: "Do I look like I'm ready to play...or distract you from your game?" - teasing(31)
-- caption_type differs. Question-based = dm_farm is more specific
UPDATE caption_bank SET content_type_id = 31, caption_type = 'dm_farm', classification_confidence = 0.85, classification_method = 'wave4_duplicate_resolver' WHERE caption_id = 19768;
UPDATE caption_bank SET content_type_id = 31, caption_type = 'dm_farm', classification_confidence = 0.85, classification_method = 'wave4_duplicate_resolver' WHERE caption_id = 60925;

-- Pair 19772/60903: "Thinking about you" - gfe(25) themed
UPDATE caption_bank SET content_type_id = 25, classification_confidence = 0.85, classification_method = 'wave4_duplicate_resolver' WHERE caption_id = 60903;

-- Pair 19774/60905: "If these pants were looser, I think they might just fall" - teasing(31)
UPDATE caption_bank SET content_type_id = 31, classification_confidence = 0.85, classification_method = 'wave4_duplicate_resolver' WHERE caption_id = 60905;

-- Pair 19775/60906: "What are we doing together on Heaven bed baby?" - teasing(31)
UPDATE caption_bank SET content_type_id = 31, classification_confidence = 0.85, classification_method = 'wave4_duplicate_resolver' WHERE caption_id = 60906;

-- Pair 19776/60907: "Shopping rule: if the mirror selfie feels right" - teasing(31)
UPDATE caption_bank SET content_type_id = 31, classification_confidence = 0.85, classification_method = 'wave4_duplicate_resolver' WHERE caption_id = 60907;

-- Pair 19777/60908: "Debating whether to button up like a good girl" - teasing(31)
-- caption_type differs. Question "What do you think?" = dm_farm is more specific
UPDATE caption_bank SET content_type_id = 31, caption_type = 'dm_farm', classification_confidence = 0.85, classification_method = 'wave4_duplicate_resolver' WHERE caption_id = 19777;

-- Pair 19778/60954: "it's okay to stare" - teasing(31)
UPDATE caption_bank SET content_type_id = 31, classification_confidence = 0.85, classification_method = 'wave4_duplicate_resolver' WHERE caption_id = 60954;

-- Pair 19779/60955: "This is your sign to message me first" - teasing(31)
-- caption_type differs: bump_descriptive vs ppv_video. This is engagement-focused, bump_descriptive is better
UPDATE caption_bank SET content_type_id = 31, caption_type = 'bump_descriptive', classification_confidence = 0.85, classification_method = 'wave4_duplicate_resolver' WHERE caption_id = 60955;

-- Pair 19781/60956: "i know exactly how to keep you hooked" - teasing(31)
UPDATE caption_bank SET content_type_id = 31, classification_confidence = 0.85, classification_method = 'wave4_duplicate_resolver' WHERE caption_id = 60956;

-- Pair 19782/60957: "just ur daily dose of distraction" - teasing(31)
UPDATE caption_bank SET content_type_id = 31, classification_confidence = 0.85, classification_method = 'wave4_duplicate_resolver' WHERE caption_id = 60957;

-- Pair 19902/61257: "DM me on my other page to book @kktbg" - exclusive_content(28)
-- caption_type differs: bump_descriptive vs ppv_video. This is promotional booking, bump_descriptive is better
UPDATE caption_bank SET content_type_id = 28, caption_type = 'bump_descriptive', classification_confidence = 0.85, classification_method = 'wave4_duplicate_resolver' WHERE caption_id = 61257;

-- Pair 19946/61248: "No tricks, just treats" - teasing(31)
UPDATE caption_bank SET content_type_id = 31, classification_confidence = 0.85, classification_method = 'wave4_duplicate_resolver' WHERE caption_id = 61248;

-- Pair 19948/61250: "It this enough hair to pull?" - teasing(31)
UPDATE caption_bank SET content_type_id = 31, classification_confidence = 0.85, classification_method = 'wave4_duplicate_resolver' WHERE caption_id = 61250;

-- Pair 19949/61251: "Raise your hand if you love fall" - teasing(31)
UPDATE caption_bank SET content_type_id = 31, classification_confidence = 0.85, classification_method = 'wave4_duplicate_resolver' WHERE caption_id = 61251;

-- Pair 19950/61252: "Sex before bed or when we wake up?" - teasing(31)
UPDATE caption_bank SET content_type_id = 31, classification_confidence = 0.85, classification_method = 'wave4_duplicate_resolver' WHERE caption_id = 61252;

-- Pair 19951/61253: "In the kitchen maken" - teasing(31)
UPDATE caption_bank SET content_type_id = 31, classification_confidence = 0.85, classification_method = 'wave4_duplicate_resolver' WHERE caption_id = 61253;

-- Pair 19952/61254: "It's been so long since a guy stretched me like this" - boy_girl(11) explicit
UPDATE caption_bank SET content_type_id = 11, classification_confidence = 0.85, classification_method = 'wave4_duplicate_resolver' WHERE caption_id = 61254;

-- Pair 20004/61232: "who wants to see the back shots?" - teasing(31)
UPDATE caption_bank SET content_type_id = 31, classification_confidence = 0.85, classification_method = 'wave4_duplicate_resolver' WHERE caption_id = 61232;

-- Pair 20007/61233: "facetime with a lucky fan" - teasing(31)
UPDATE caption_bank SET content_type_id = 31, classification_confidence = 0.85, classification_method = 'wave4_duplicate_resolver' WHERE caption_id = 61233;

-- Pair 20067/61172: "i wont tell if you dont..." - teasing(31)
UPDATE caption_bank SET content_type_id = 31, classification_confidence = 0.85, classification_method = 'wave4_duplicate_resolver' WHERE caption_id = 61172;

-- Pair 20068/61173: "hope you all have had a happy holiday week so far!" - teasing(31)
UPDATE caption_bank SET content_type_id = 31, classification_confidence = 0.85, classification_method = 'wave4_duplicate_resolver' WHERE caption_id = 61173;

-- Pair 20083/61215: "see me get spanked... hard" - dom_sub(14) fetish
UPDATE caption_bank SET content_type_id = 14, classification_confidence = 0.85, classification_method = 'wave4_duplicate_resolver' WHERE caption_id = 61215;

-- Pair 20084/61216: "NUDES?" with link - solo(19) explicit
UPDATE caption_bank SET content_type_id = 19, classification_confidence = 0.85, classification_method = 'wave4_duplicate_resolver' WHERE caption_id = 61216;

-- Pair 20103/61142: "Today feels like a good playlist on repeat kinda day" - teasing(31)
UPDATE caption_bank SET content_type_id = 31, classification_confidence = 0.85, classification_method = 'wave4_duplicate_resolver' WHERE caption_id = 61142;

-- Pair 20104/61143: "Sunday is made for pleasure" - pool_outdoor(21) themed
UPDATE caption_bank SET content_type_id = 21, classification_confidence = 0.85, classification_method = 'wave4_duplicate_resolver' WHERE caption_id = 61143;

-- Pair 20105/61144: "Making Drinks with My Eyes Closed" - boy_girl(11) (video challenge content)
UPDATE caption_bank SET content_type_id = 11, classification_confidence = 0.85, classification_method = 'wave4_duplicate_resolver' WHERE caption_id = 61144;

-- Pair 20106/61145: "Rubber Band Challenge" - teasing(31)
UPDATE caption_bank SET content_type_id = 31, classification_confidence = 0.85, classification_method = 'wave4_duplicate_resolver' WHERE caption_id = 61145;

-- Pair 20107/61146: "Long day is finally over" - teasing(31)
UPDATE caption_bank SET content_type_id = 31, classification_confidence = 0.85, classification_method = 'wave4_duplicate_resolver' WHERE caption_id = 61146;

-- Pair 20108/61147: "Just sending out some positive vibes today" - teasing(31)
-- caption_type differs: bump_descriptive vs ppv_video. This is engagement, bump_descriptive is better
UPDATE caption_bank SET content_type_id = 31, caption_type = 'bump_descriptive', classification_confidence = 0.85, classification_method = 'wave4_duplicate_resolver' WHERE caption_id = 61147;

-- Pair 20109/61148: "If you could teleport anywhere right now?" - teasing(31)
-- caption_type differs. Question = dm_farm is more specific
UPDATE caption_bank SET content_type_id = 31, caption_type = 'dm_farm', classification_confidence = 0.85, classification_method = 'wave4_duplicate_resolver' WHERE caption_id = 20109;
UPDATE caption_bank SET content_type_id = 31, caption_type = 'dm_farm', classification_confidence = 0.85, classification_method = 'wave4_duplicate_resolver' WHERE caption_id = 61148;

-- Pair 20110/61149: "Decided to run some errands today" - pool_outdoor(21) themed
UPDATE caption_bank SET content_type_id = 21, classification_confidence = 0.85, classification_method = 'wave4_duplicate_resolver' WHERE caption_id = 61149;

-- Pair 20111/61150: "Challenge: Ping Pong Ball Tricks" - teasing(31)
UPDATE caption_bank SET content_type_id = 31, classification_confidence = 0.85, classification_method = 'wave4_duplicate_resolver' WHERE caption_id = 61150;

-- Pair 20119/61160: "who's brave enough to slide first?" - implied_tits_play(36) teasing
UPDATE caption_bank SET content_type_id = 36, classification_confidence = 0.85, classification_method = 'wave4_duplicate_resolver' WHERE caption_id = 61160;

-- Pair 20120/61161: "you know where to find me" - teasing(31)
UPDATE caption_bank SET content_type_id = 31, classification_confidence = 0.85, classification_method = 'wave4_duplicate_resolver' WHERE caption_id = 61161;

-- Pair 20121/61140: "first thought that pops in your head right now?" - teasing(31)
UPDATE caption_bank SET content_type_id = 31, classification_confidence = 0.85, classification_method = 'wave4_duplicate_resolver' WHERE caption_id = 61140;

-- Pair 20124/61163: "dm me your favorite emoji combo" - teasing(31)
-- caption_type differs: bump_descriptive vs ppv_video. DM request = bump_descriptive is better
UPDATE caption_bank SET content_type_id = 31, caption_type = 'bump_descriptive', classification_confidence = 0.85, classification_method = 'wave4_duplicate_resolver' WHERE caption_id = 61163;

-- Pair 20125/61137: "what's the verdict outfit or view" - teasing(31)
UPDATE caption_bank SET content_type_id = 31, classification_confidence = 0.85, classification_method = 'wave4_duplicate_resolver' WHERE caption_id = 61137;

-- Pair 20126/61164: "the kind of night that lingers" - teasing(31)
UPDATE caption_bank SET content_type_id = 31, classification_confidence = 0.85, classification_method = 'wave4_duplicate_resolver' WHERE caption_id = 61164;

-- Pair 20129/61184: "Things always get pretty steamy on vacation" - implied_tits_play(36) teasing
UPDATE caption_bank SET content_type_id = 36, classification_confidence = 0.85, classification_method = 'wave4_duplicate_resolver' WHERE caption_id = 61184;

-- Pair 20133/61188: "Do you prefer just seeing me barefoot?" - teasing(31)
UPDATE caption_bank SET content_type_id = 31, classification_confidence = 0.85, classification_method = 'wave4_duplicate_resolver' WHERE caption_id = 61188;

-- Pair 20135/61190: "All green in the garden" - implied_tits_play(36) teasing
UPDATE caption_bank SET content_type_id = 36, classification_confidence = 0.85, classification_method = 'wave4_duplicate_resolver' WHERE caption_id = 61190;

-- Pair 20155/61084: "Love to go in a gym so much" - teasing(31)
UPDATE caption_bank SET content_type_id = 31, classification_confidence = 0.85, classification_method = 'wave4_duplicate_resolver' WHERE caption_id = 61084;

-- Pair 20157/61086: "Which your plans on this week?" - teasing(31)
UPDATE caption_bank SET content_type_id = 31, classification_confidence = 0.85, classification_method = 'wave4_duplicate_resolver' WHERE caption_id = 61086;

-- Pair 20175/61139: "first thing you noticed be honest" - teasing(31)
UPDATE caption_bank SET content_type_id = 31, classification_confidence = 0.85, classification_method = 'wave4_duplicate_resolver' WHERE caption_id = 61139;

-- Pair 20177/61106: "Look like black cat" - teasing(31)
UPDATE caption_bank SET content_type_id = 31, classification_confidence = 0.85, classification_method = 'wave4_duplicate_resolver' WHERE caption_id = 61106;

-- Pair 20178/61107: "I love animals very much" - teasing(31)
-- caption_type differs. Question "Would you like me to tell you?" = dm_farm is more specific
UPDATE caption_bank SET content_type_id = 31, caption_type = 'dm_farm', classification_confidence = 0.85, classification_method = 'wave4_duplicate_resolver' WHERE caption_id = 20178;
UPDATE caption_bank SET content_type_id = 31, caption_type = 'dm_farm', classification_confidence = 0.85, classification_method = 'wave4_duplicate_resolver' WHERE caption_id = 61107;

-- Pair 20179/61108: "Time to walking with favorite music" - teasing(31)
UPDATE caption_bank SET content_type_id = 31, classification_confidence = 0.85, classification_method = 'wave4_duplicate_resolver' WHERE caption_id = 61108;

-- Pair 20183/61087: "I must to return and buy this dress" - teasing(31)
UPDATE caption_bank SET content_type_id = 31, classification_confidence = 0.85, classification_method = 'wave4_duplicate_resolver' WHERE caption_id = 61087;

-- Pair 20184/61088: "I love sport so much" - teasing(31)
UPDATE caption_bank SET content_type_id = 31, classification_confidence = 0.85, classification_method = 'wave4_duplicate_resolver' WHERE caption_id = 61088;

-- Pair 20236/60928: "thinking about me?" - teasing(31)
UPDATE caption_bank SET content_type_id = 31, classification_confidence = 0.85, classification_method = 'wave4_duplicate_resolver' WHERE caption_id = 60928;

-- Pair 20239/60931: "Girl of your dreams" - teasing(31)
UPDATE caption_bank SET content_type_id = 31, classification_confidence = 0.85, classification_method = 'wave4_duplicate_resolver' WHERE caption_id = 60931;

-- Pair 20241/60933: "Say 'Hi' and let's find out your limits" - teasing(31)
UPDATE caption_bank SET content_type_id = 31, classification_confidence = 0.85, classification_method = 'wave4_duplicate_resolver' WHERE caption_id = 60933;

-- Pair 20260/61264: "Simple moments, big feelings" - teasing(31)
UPDATE caption_bank SET content_type_id = 31, classification_confidence = 0.85, classification_method = 'wave4_duplicate_resolver' WHERE caption_id = 61264;

-- Pair 20261/61266: "Some days are made for slow mornings" - teasing(31)
UPDATE caption_bank SET content_type_id = 31, classification_confidence = 0.85, classification_method = 'wave4_duplicate_resolver' WHERE caption_id = 61266;

-- Pair 20264/61177: "I came, trained, took pictures" - teasing(31)
UPDATE caption_bank SET content_type_id = 31, classification_confidence = 0.85, classification_method = 'wave4_duplicate_resolver' WHERE caption_id = 61177;

-- Pair 20266/61181: "I once heard a phrase: if you don't move, nothing moves" - teasing(31)
UPDATE caption_bank SET content_type_id = 31, classification_confidence = 0.85, classification_method = 'wave4_duplicate_resolver' WHERE caption_id = 61181;

-- Pair 20307/61122: "Who wants to help me play on this gaming chair?" - teasing(31)
UPDATE caption_bank SET content_type_id = 31, classification_confidence = 0.85, classification_method = 'wave4_duplicate_resolver' WHERE caption_id = 61122;

-- Pair 20310/61125: "your favorite cake is served" - teasing(31)
UPDATE caption_bank SET content_type_id = 31, classification_confidence = 0.85, classification_method = 'wave4_duplicate_resolver' WHERE caption_id = 61125;

-- Pair 20324/61012: "This is me at my sweetest" - teasing(31)
UPDATE caption_bank SET content_type_id = 31, classification_confidence = 0.85, classification_method = 'wave4_duplicate_resolver' WHERE caption_id = 61012;

-- Pair 20374/61026: "This couch needs your handprints next" - teasing(31)
UPDATE caption_bank SET content_type_id = 31, classification_confidence = 0.85, classification_method = 'wave4_duplicate_resolver' WHERE caption_id = 61026;

-- Pair 20375/61027: "Legs wide, your turn" - implied_solo(35) teasing
UPDATE caption_bank SET content_type_id = 35, classification_confidence = 0.85, classification_method = 'wave4_duplicate_resolver' WHERE caption_id = 61027;

-- Pair 20376/61028: "This spot's officially mine now" - flash_sale(27) promotional
UPDATE caption_bank SET content_type_id = 27, classification_confidence = 0.85, classification_method = 'wave4_duplicate_resolver' WHERE caption_id = 61028;

-- Pair 20425/60959: "Can you handle this?" - teasing(31)
UPDATE caption_bank SET content_type_id = 31, classification_confidence = 0.85, classification_method = 'wave4_duplicate_resolver' WHERE caption_id = 60959;

-- Pair 20426/61180: "Enjoying the last days of autumn" - teasing(31)
-- caption_type differs: bump_descriptive vs ppv_video. Engagement/lifestyle content, bump_descriptive is better
UPDATE caption_bank SET content_type_id = 31, caption_type = 'bump_descriptive', classification_confidence = 0.85, classification_method = 'wave4_duplicate_resolver' WHERE caption_id = 61180;

-- Pair 20448/61213: "Still available!" with link - exclusive_content(28) promotional
UPDATE caption_bank SET content_type_id = 28, classification_confidence = 0.85, classification_method = 'wave4_duplicate_resolver' WHERE caption_id = 61213;

-- Pair 20450/60916: "This bikini's lonely without your teeth marks" - pool_outdoor(21) themed
UPDATE caption_bank SET content_type_id = 21, classification_confidence = 0.85, classification_method = 'wave4_duplicate_resolver' WHERE caption_id = 60916;

-- Pair 20452/61011: "Caught you looking again... ready to confess your thoughts?" - teasing(31)
-- caption_type differs. Question "ready to confess?" = dm_farm is more specific
UPDATE caption_bank SET content_type_id = 31, caption_type = 'dm_farm', classification_confidence = 0.85, classification_method = 'wave4_duplicate_resolver' WHERE caption_id = 20452;
UPDATE caption_bank SET content_type_id = 31, caption_type = 'dm_farm', classification_confidence = 0.85, classification_method = 'wave4_duplicate_resolver' WHERE caption_id = 61011;

-- -----------------------------------------------------------------------------
-- GROUP 2: Conflicting content_type_id Resolution (analyze text to determine correct type)
-- Both records have content_type_id but different values
-- -----------------------------------------------------------------------------

-- Pair 19690/61262: "Come play with me today, love... I'm in the mood to tease you"
-- Both have content_type_id=31 (teasing) - types differ: bump_descriptive vs bump_normal
-- bump_descriptive is more accurate for this descriptive, longer caption
UPDATE caption_bank SET caption_type = 'bump_descriptive', classification_confidence = 0.85, classification_method = 'wave4_duplicate_resolver' WHERE caption_id = 61262;

-- Pair 19714/61236: "Tip $5 boob pic Tip $10 surprise hot vid"
-- id1: first_to_tip, content_type_id=32 (tip_request)
-- id2: ppv_video, content_type_id=18 (tits_play)
-- This is a tip menu with explicit content - tip_request(32) is correct category, first_to_tip is correct caption_type
UPDATE caption_bank SET caption_type = 'first_to_tip', content_type_id = 32, classification_confidence = 0.85, classification_method = 'wave4_duplicate_resolver' WHERE caption_id = 61236;

-- Pair 19731/61004: "done with homework, should i do u now?"
-- Both have content_type_id=31 (teasing) - types differ: bump_normal vs dm_farm
-- Question format = dm_farm is more specific
UPDATE caption_bank SET caption_type = 'dm_farm', classification_confidence = 0.85, classification_method = 'wave4_duplicate_resolver' WHERE caption_id = 19731;

-- Pair 19745/60941: "A little picture series with my pink fuzzy bra for you!"
-- id1: content_type_id=36 (implied_tits_play)
-- id2: content_type_id=22 (lingerie)
-- Bra = lingerie is more accurate than implied_tits_play
UPDATE caption_bank SET content_type_id = 22, classification_confidence = 0.85, classification_method = 'wave4_duplicate_resolver' WHERE caption_id = 19745;

-- Pair 19748/60887: "Throwback to this set that I loved so much!"
-- id1: content_type_id=31 (teasing)
-- id2: content_type_id=26 (bundle_offer)
-- "Set" could mean bundle - but throwback is just teasing engagement content
UPDATE caption_bank SET content_type_id = 31, classification_confidence = 0.85, classification_method = 'wave4_duplicate_resolver' WHERE caption_id = 60887;

-- Pair 19769/60926: "Oops! Wardrobe malfunction... Wanna help me fix it?"
-- id1: content_type_id=19 (solo)
-- id2: content_type_id=31 (teasing)
-- Wardrobe malfunction is more teasing than solo explicit
UPDATE caption_bank SET content_type_id = 31, classification_confidence = 0.85, classification_method = 'wave4_duplicate_resolver' WHERE caption_id = 19769;

-- Pair 20086/61214: "CYBER MONDAY PUSSY + TITS DEAL!"
-- id1: bump_descriptive, content_type_id=18 (tits_play)
-- id2: ppv_video, content_type_id=16 (pussy_play)
-- This is a promotional PPV bundle - pussy_play(16) is more explicit, ppv_video is correct caption_type
UPDATE caption_bank SET caption_type = 'ppv_video', content_type_id = 16, classification_confidence = 0.85, classification_method = 'wave4_duplicate_resolver' WHERE caption_id = 20086;

-- Pair 20114/61179: "There was a post about sports recently..."
-- Both have content_type_id=31 (teasing) - types differ: bump_descriptive vs dm_farm
-- "share them in the comments" = engagement, dm_farm is more specific
UPDATE caption_bank SET caption_type = 'dm_farm', classification_confidence = 0.85, classification_method = 'wave4_duplicate_resolver' WHERE caption_id = 20114;

-- Pair 20130/61185: "It's my Birthday! (JOI) Stroke faster as I undress..."
-- id1: content_type_id=12 (joi)
-- id2: content_type_id=16 (pussy_play)
-- JOI is explicitly mentioned - joi(12) is correct
UPDATE caption_bank SET content_type_id = 12, classification_confidence = 0.85, classification_method = 'wave4_duplicate_resolver' WHERE caption_id = 61185;

-- Pair 20134/61189: "POV: Your sweet girlfriend loves teasing & playing with your dick"
-- id1: content_type_id=24 (pov)
-- id2: content_type_id=31 (teasing)
-- "POV:" is explicitly mentioned - pov(24) is correct
UPDATE caption_bank SET content_type_id = 24, classification_confidence = 0.85, classification_method = 'wave4_duplicate_resolver' WHERE caption_id = 61189;

-- Pair 20154/61083: "SPECIAL BUNDLE... my pussy... dildo..."
-- id1: bump_descriptive, content_type_id=17 (toy_play)
-- id2: ppv_video, content_type_id=16 (pussy_play)
-- Mentions dildo/toy - toy_play(17) is more specific. This is PPV content.
UPDATE caption_bank SET caption_type = 'ppv_video', content_type_id = 17, classification_confidence = 0.85, classification_method = 'wave4_duplicate_resolver' WHERE caption_id = 20154;
UPDATE caption_bank SET caption_type = 'ppv_video', content_type_id = 17, classification_confidence = 0.85, classification_method = 'wave4_duplicate_resolver' WHERE caption_id = 61083;

-- Pair 20185/61089: "Oh honey, finally, I did it for you... hottest lingerie..."
-- id1: content_type_id=22 (lingerie)
-- id2: content_type_id=16 (pussy_play)
-- Mentions lingerie AND explicit pussy content - pussy_play(16) is more explicit (priority)
UPDATE caption_bank SET content_type_id = 16, classification_confidence = 0.85, classification_method = 'wave4_duplicate_resolver' WHERE caption_id = 20185;

-- Pair 20203/61170: "succubus gets stuffed and pumped by huge monster toy!"
-- id1: content_type_id=31 (teasing)
-- id2: content_type_id=17 (toy_play)
-- Explicit toy content - toy_play(17) is more accurate
UPDATE caption_bank SET content_type_id = 17, classification_confidence = 0.85, classification_method = 'wave4_duplicate_resolver' WHERE caption_id = 20203;

-- Pair 20308/61123: "DM me if you want to see what I did after this picture"
-- Both have content_type_id=31 (teasing) - types differ: bump_descriptive vs ppv_video
-- This is teaser for PPV content - bump_descriptive is for engagement/teasing
UPDATE caption_bank SET caption_type = 'bump_descriptive', classification_confidence = 0.85, classification_method = 'wave4_duplicate_resolver' WHERE caption_id = 61123;

-- Pair 20309/61124: "Do you want to see me take this off?"
-- id1: content_type_id=27 (flash_sale)
-- id2: content_type_id=31 (teasing)
-- This is teasing content, not a flash sale - teasing(31) is correct
UPDATE caption_bank SET content_type_id = 31, classification_confidence = 0.85, classification_method = 'wave4_duplicate_resolver' WHERE caption_id = 20309;

-- Pair 20373/61024: "She's teasing you... in that wet shirt... fucks herself until she squirts"
-- id1: content_type_id=3 (unknown/other)
-- id2: content_type_id=16 (pussy_play)
-- Explicit squirt content - pussy_play(16) is correct
UPDATE caption_bank SET content_type_id = 16, classification_confidence = 0.85, classification_method = 'wave4_duplicate_resolver' WHERE caption_id = 20373;

-- Pair 20394/61169: "hi down there :)"
-- id1: content_type_id=31 (teasing)
-- id2: content_type_id=34 (implied_pussy_play)
-- "down there" suggests implied_pussy_play(34) is more accurate
UPDATE caption_bank SET content_type_id = 34, classification_confidence = 0.85, classification_method = 'wave4_duplicate_resolver' WHERE caption_id = 20394;

-- Pair 20449/60915: "Covering my tits and pussy like a good girl... not"
-- id1: content_type_id=18 (tits_play)
-- id2: content_type_id=16 (pussy_play)
-- Mentions both tits AND pussy - pussy is more explicit (priority)
UPDATE caption_bank SET content_type_id = 16, classification_confidence = 0.85, classification_method = 'wave4_duplicate_resolver' WHERE caption_id = 20449;

-- Pair 20451/60917: "Black top, wet thoughts"
-- id1: content_type_id=31 (teasing)
-- id2: content_type_id=16 (pussy_play)
-- "wet thoughts" is suggestive but not explicit - teasing(31) is correct
UPDATE caption_bank SET content_type_id = 31, classification_confidence = 0.85, classification_method = 'wave4_duplicate_resolver' WHERE caption_id = 60917;

-- -----------------------------------------------------------------------------
-- VERIFICATION: Update classification metadata for all records in pairs
-- Ensure the canonical record also has updated classification metadata
-- -----------------------------------------------------------------------------

-- Update the "source" records that already had correct content_type_id
UPDATE caption_bank
SET classification_confidence = 0.85, classification_method = 'wave4_duplicate_resolver'
WHERE caption_id IN (
    19662, 19663, 19664, 19665, 19666, 19670, 19673, 19690, 19713, 19714,
    19729, 19730, 19731, 19732, 19733, 19734, 19735, 19739, 19740, 19742,
    19743, 19744, 19745, 19746, 19747, 19748, 19750, 19755, 19757, 19758,
    19759, 19762, 19763, 19764, 19766, 19767, 19768, 19769, 19772, 19774,
    19775, 19776, 19777, 19778, 19779, 19781, 19782, 19902, 19946, 19948,
    19949, 19950, 19951, 19952, 20004, 20007, 20067, 20068, 20083, 20084,
    20086, 20103, 20104, 20105, 20106, 20107, 20108, 20109, 20110, 20111,
    20114, 20119, 20120, 20121, 20124, 20125, 20126, 20129, 20130, 20133,
    20134, 20135, 20154, 20155, 20157, 20175, 20177, 20178, 20179, 20183,
    20184, 20185, 20203, 20236, 20239, 20241, 20260, 20261, 20264, 20266,
    20307, 20308, 20309, 20310, 20324, 20373, 20374, 20375, 20376, 20394,
    20425, 20426, 20448, 20449, 20450, 20451, 20452
);

COMMIT;

-- =============================================================================
-- VERIFICATION QUERIES (Run after script execution)
-- =============================================================================

-- Verify no remaining duplicate pairs with inconsistent classifications
-- Expected result: 0 rows
-- SELECT 'Remaining inconsistent pairs:' as check_type, COUNT(*) as count
-- FROM caption_bank cb1
-- JOIN caption_bank cb2 ON cb1.caption_text = cb2.caption_text AND cb1.caption_id < cb2.caption_id
-- WHERE cb1.caption_type != cb2.caption_type OR COALESCE(cb1.content_type_id, -1) != COALESCE(cb2.content_type_id, -1);

-- Count of records updated by this wave
-- SELECT 'Records updated by wave4_duplicate_resolver:' as check_type, COUNT(*) as count
-- FROM caption_bank
-- WHERE classification_method = 'wave4_duplicate_resolver';

-- Distribution of content types after resolution
-- SELECT content_type_id, COUNT(*) as count
-- FROM caption_bank
-- WHERE classification_method = 'wave4_duplicate_resolver'
-- GROUP BY content_type_id
-- ORDER BY count DESC;

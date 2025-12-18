-- Wave 4: High-Value Caption Reclassification
-- Purpose: Reclassify high-value captions (performance_score >= 70) with low confidence (< 0.7)
-- Method: wave4_high_value_reclassifier
-- Date: 2025-12-15

-- ============================================================================
-- CONTENT TYPE REFERENCE:
-- ============================================================================
-- 1  = anal (explicit) - anal, ass fuck, DP
-- 2  = creampie (explicit) - creampie, cum inside, filled
-- 3  = squirting (explicit) - squirt, fountain, gush
-- 4  = threesome_group (explicit) - threesome, 3some, MMF, FFM, orgy
-- 7  = deepthroat (explicit) - deepthroat, throat
-- 8  = blowjob (explicit) - blowjob, suck, BJ, mouth
-- 11 = boy_girl (explicit) - fuck, sex, partner, railed, pounded
-- 12 = joi (interactive) - stroke, jerk, cum for me, instructions
-- 13 = feet (fetish) - feet, toes, soles
-- 14 = dom_sub (fetish) - master, slave, obey, pet
-- 16 = pussy_play (solo_explicit) - pussy, wet, play with myself
-- 17 = toy_play (solo_explicit) - toy, dildo, vibrator
-- 18 = tits_play (solo_explicit) - tits, boobs, titty, bouncing
-- 19 = solo (solo_explicit) - solo, masturbate
-- 20 = shower_bath (themed) - shower, bath, wet
-- 21 = pool_outdoor (themed) - pool, beach, outdoor, bikini
-- 22 = lingerie (themed) - lingerie, bra, panties, outfit
-- 24 = pov (themed) - pov, your view
-- 25 = gfe (themed) - girlfriend, gfe, cuddle
-- 26 = bundle_offer (promotional) - bundle, pack, collection
-- 27 = flash_sale (promotional) - sale, discount, off
-- 28 = exclusive_content (promotional) - exclusive, special, vip
-- 30 = nude (solo) - nude, naked
-- 31 = teasing (engagement) - flirty, thinking of you, general tease
-- 32 = tip_request (engagement) - tip, $, reward
-- 33 = renewal_retention (engagement) - renew, subscribe, stay
-- 34 = implied_pussy_play (teasing)
-- 35 = implied_solo (teasing)
-- 36 = implied_tits_play (teasing)
-- 37 = implied_toy_play (teasing)
-- ============================================================================

BEGIN TRANSACTION;

-- ============================================================================
-- CATEGORY: BOY_GIRL (11) - Explicit sex with partner
-- Captions describing fucking, sex, partner sex, getting railed/pounded
-- ============================================================================

-- Caption 13: "Your Habibi is Ready to get Fucked in these positions" - describes getting fucked
UPDATE caption_bank SET content_type_id = 11, classification_confidence = 0.90, classification_method = 'wave4_high_value_reclassifier' WHERE caption_id = 13;

-- Caption 24: "MY FIRST SEX TAPE...see me get fucked and love it" - explicit sex tape
UPDATE caption_bank SET content_type_id = 11, classification_confidence = 0.90, classification_method = 'wave4_high_value_reclassifier' WHERE caption_id = 24;

-- Caption 84: "tittys bounce while getting my little pussy fucked" - b/g sex
UPDATE caption_bank SET content_type_id = 11, classification_confidence = 0.90, classification_method = 'wave4_high_value_reclassifier' WHERE caption_id = 84;

-- Caption 116: "me and jared were super horny...two videos" - b/g content
UPDATE caption_bank SET content_type_id = 11, classification_confidence = 0.90, classification_method = 'wave4_high_value_reclassifier' WHERE caption_id = 116;

-- Caption 123: "watch this moody cowgirl clip, I love riding" - riding = b/g sex
UPDATE caption_bank SET content_type_id = 11, classification_confidence = 0.90, classification_method = 'wave4_high_value_reclassifier' WHERE caption_id = 123;

-- Caption 530: "really wanted head...gave him that good good head" - oral with partner
UPDATE caption_bank SET content_type_id = 8, classification_confidence = 0.90, classification_method = 'wave4_high_value_reclassifier' WHERE caption_id = 530;

-- Caption 533: "sharing cock and sharing cum" - b/g sex
UPDATE caption_bank SET content_type_id = 11, classification_confidence = 0.90, classification_method = 'wave4_high_value_reclassifier' WHERE caption_id = 533;

-- Caption 534: "SEXTAPE!! fucked me in doggy...tried full Nelson" - explicit b/g
UPDATE caption_bank SET content_type_id = 11, classification_confidence = 0.90, classification_method = 'wave4_high_value_reclassifier' WHERE caption_id = 534;

-- Caption 535: "pussy is so wet while im getting drilled" - b/g sex
UPDATE caption_bank SET content_type_id = 11, classification_confidence = 0.90, classification_method = 'wave4_high_value_reclassifier' WHERE caption_id = 535;

-- Caption 557: "sextapes...see me take his backshots" - b/g sex
UPDATE caption_bank SET content_type_id = 11, classification_confidence = 0.90, classification_method = 'wave4_high_value_reclassifier' WHERE caption_id = 557;

-- Caption 560: "I was this flexible while i get fucked" - b/g sex
UPDATE caption_bank SET content_type_id = 11, classification_confidence = 0.90, classification_method = 'wave4_high_value_reclassifier' WHERE caption_id = 560;

-- Caption 576: "full sex tape...doggy, riding, missionary, backshots" - b/g sex
UPDATE caption_bank SET content_type_id = 11, classification_confidence = 0.90, classification_method = 'wave4_high_value_reclassifier' WHERE caption_id = 576;

-- Caption 593: "first sextapes...take the backshoots" - b/g sex
UPDATE caption_bank SET content_type_id = 11, classification_confidence = 0.90, classification_method = 'wave4_high_value_reclassifier' WHERE caption_id = 593;

-- Caption 620: "tight pussy getting railed from behind" - b/g sex
UPDATE caption_bank SET content_type_id = 11, classification_confidence = 0.90, classification_method = 'wave4_high_value_reclassifier' WHERE caption_id = 620;

-- Caption 633: "BG sex tape in the backseat" - b/g sex
UPDATE caption_bank SET content_type_id = 11, classification_confidence = 0.90, classification_method = 'wave4_high_value_reclassifier' WHERE caption_id = 633;

-- Caption 636: "playing with my pussy in my car" - solo in car
UPDATE caption_bank SET content_type_id = 16, classification_confidence = 0.90, classification_method = 'wave4_high_value_reclassifier' WHERE caption_id = 636;

-- Caption 744: "Sloppy facefuck with facial cumshot" - b/g oral/facial
UPDATE caption_bank SET content_type_id = 8, classification_confidence = 0.90, classification_method = 'wave4_high_value_reclassifier' WHERE caption_id = 744;

-- Caption 792: "Watch me getting fucked while on standing position" - b/g sex
UPDATE caption_bank SET content_type_id = 11, classification_confidence = 0.90, classification_method = 'wave4_high_value_reclassifier' WHERE caption_id = 792;

-- Caption 807: "Hands tied, moaning, groaping, getting railed" - b/g sex
UPDATE caption_bank SET content_type_id = 11, classification_confidence = 0.90, classification_method = 'wave4_high_value_reclassifier' WHERE caption_id = 807;

-- ============================================================================
-- CATEGORY: BLOWJOB (8) - Oral sex focused content
-- ============================================================================

-- Caption 7: Already correctly classified as 7 (deepthroat) - VERIFY ONLY
UPDATE caption_bank SET classification_confidence = 0.90, classification_method = 'wave4_high_value_reclassifier' WHERE caption_id = 7 AND content_type_id = 7;

-- Caption 54: "BBC sex video...BJ and getting titty fucked" - has BJ but primarily b/g
UPDATE caption_bank SET content_type_id = 11, classification_confidence = 0.90, classification_method = 'wave4_high_value_reclassifier' WHERE caption_id = 54;

-- Caption 96: "POV of me sucking and jerking daddy off" - blowjob focused
UPDATE caption_bank SET content_type_id = 8, classification_confidence = 0.90, classification_method = 'wave4_high_value_reclassifier' WHERE caption_id = 96;

-- Caption 155: Already correctly classified as 7 (deepthroat) - VERIFY ONLY
UPDATE caption_bank SET classification_confidence = 0.90, classification_method = 'wave4_high_value_reclassifier' WHERE caption_id = 155 AND content_type_id = 7;

-- Caption 541: "sloppy bj...being a good slut" - blowjob
UPDATE caption_bank SET content_type_id = 8, classification_confidence = 0.90, classification_method = 'wave4_high_value_reclassifier' WHERE caption_id = 541;

-- Caption 552: "sex tape / b/g scene...sucking dick" - b/g sex
UPDATE caption_bank SET content_type_id = 11, classification_confidence = 0.90, classification_method = 'wave4_high_value_reclassifier' WHERE caption_id = 552;

-- Caption 563: "sloppy blowjob...cumshot facial" - blowjob with facial
UPDATE caption_bank SET content_type_id = 8, classification_confidence = 0.90, classification_method = 'wave4_high_value_reclassifier' WHERE caption_id = 563;

-- Caption 596: "great blowjob until he cums in my mouth" - blowjob
UPDATE caption_bank SET content_type_id = 8, classification_confidence = 0.90, classification_method = 'wave4_high_value_reclassifier' WHERE caption_id = 596;

-- Caption 597: "long sloppy blowjob video with cumshot" - blowjob
UPDATE caption_bank SET content_type_id = 8, classification_confidence = 0.90, classification_method = 'wave4_high_value_reclassifier' WHERE caption_id = 597;

-- Caption 602: "sneak peek of how good I suck cock" - blowjob
UPDATE caption_bank SET content_type_id = 8, classification_confidence = 0.90, classification_method = 'wave4_high_value_reclassifier' WHERE caption_id = 602;

-- Caption 705: "How do I look with a real cock in my mouth" - blowjob
UPDATE caption_bank SET content_type_id = 8, classification_confidence = 0.90, classification_method = 'wave4_high_value_reclassifier' WHERE caption_id = 705;

-- Caption 736: Already correctly classified as 7 (deepthroat) - VERIFY ONLY
UPDATE caption_bank SET classification_confidence = 0.90, classification_method = 'wave4_high_value_reclassifier' WHERE caption_id = 736 AND content_type_id = 7;

-- Caption 778: "fucks my throat for 5 minutes...most sexy blowjob" - deepthroat
UPDATE caption_bank SET content_type_id = 7, classification_confidence = 0.90, classification_method = 'wave4_high_value_reclassifier' WHERE caption_id = 778;

-- ============================================================================
-- CATEGORY: THREESOME_GROUP (4) - Multiple partners
-- ============================================================================

-- Caption 55: "first FFM threesome" - Already correctly 4, VERIFY
UPDATE caption_bank SET classification_confidence = 0.90, classification_method = 'wave4_high_value_reclassifier' WHERE caption_id = 55 AND content_type_id = 4;

-- Caption 77: "new MMF - both guys fuck me" - Already correctly 4, VERIFY
UPDATE caption_bank SET classification_confidence = 0.90, classification_method = 'wave4_high_value_reclassifier' WHERE caption_id = 77 AND content_type_id = 4;

-- Caption 99: "new MMF - rough sex / spit roast" - Already correctly 4, VERIFY
UPDATE caption_bank SET classification_confidence = 0.90, classification_method = 'wave4_high_value_reclassifier' WHERE caption_id = 99 AND content_type_id = 4;

-- Caption 111: "new MMF video with the 2nd fan" - Already correctly 4, VERIFY
UPDATE caption_bank SET classification_confidence = 0.90, classification_method = 'wave4_high_value_reclassifier' WHERE caption_id = 111 AND content_type_id = 4;

-- Caption 112: "new MMF 3some" - Already correctly 4, VERIFY
UPDATE caption_bank SET classification_confidence = 0.90, classification_method = 'wave4_high_value_reclassifier' WHERE caption_id = 112 AND content_type_id = 4;

-- Caption 128: "new BBG THREESOME" - Already correctly 4, VERIFY
UPDATE caption_bank SET classification_confidence = 0.90, classification_method = 'wave4_high_value_reclassifier' WHERE caption_id = 128 AND content_type_id = 4;

-- Caption 136: "threesome with CJ MILES & ALEX MACK" - Already correctly 4, VERIFY
UPDATE caption_bank SET classification_confidence = 0.90, classification_method = 'wave4_high_value_reclassifier' WHERE caption_id = 136 AND content_type_id = 4;

-- Caption 186: "BLOOPER stripper MMF scene" - Already correctly 4, VERIFY
UPDATE caption_bank SET classification_confidence = 0.90, classification_method = 'wave4_high_value_reclassifier' WHERE caption_id = 186 AND content_type_id = 4;

-- Caption 193: "new BBG THREESOME" - Already correctly 4, VERIFY
UPDATE caption_bank SET classification_confidence = 0.90, classification_method = 'wave4_high_value_reclassifier' WHERE caption_id = 193 AND content_type_id = 4;

-- Caption 227: "NEW 3some BBG" - Already correctly 4, VERIFY
UPDATE caption_bank SET classification_confidence = 0.90, classification_method = 'wave4_high_value_reclassifier' WHERE caption_id = 227 AND content_type_id = 4;

-- Caption 228: "new FFM 3some" - Already correctly 4, VERIFY
UPDATE caption_bank SET classification_confidence = 0.90, classification_method = 'wave4_high_value_reclassifier' WHERE caption_id = 228 AND content_type_id = 4;

-- Caption 230: "new FFM threesome" - Already correctly 4, VERIFY
UPDATE caption_bank SET classification_confidence = 0.90, classification_method = 'wave4_high_value_reclassifier' WHERE caption_id = 230 AND content_type_id = 4;

-- Caption 246: "new BBG 3some" - Already correctly 4, VERIFY
UPDATE caption_bank SET classification_confidence = 0.90, classification_method = 'wave4_high_value_reclassifier' WHERE caption_id = 246 AND content_type_id = 4;

-- ============================================================================
-- CATEGORY: SQUIRTING (3) - Squirting focused content
-- ============================================================================

-- Caption 78: "BWC...multiple squirting shots" - Already correctly 3, VERIFY
UPDATE caption_bank SET classification_confidence = 0.90, classification_method = 'wave4_high_value_reclassifier' WHERE caption_id = 78 AND content_type_id = 3;

-- Caption 80: "i squirted in the backseat" - Already correctly 3, VERIFY
UPDATE caption_bank SET classification_confidence = 0.90, classification_method = 'wave4_high_value_reclassifier' WHERE caption_id = 80 AND content_type_id = 3;

-- Caption 87: "BBC pornstar...made me squirt so many times" - Already correctly 3, VERIFY
UPDATE caption_bank SET classification_confidence = 0.90, classification_method = 'wave4_high_value_reclassifier' WHERE caption_id = 87 AND content_type_id = 3;

-- Caption 103: "Johnny Sins...squirt like a fountain" - Already correctly 3, VERIFY
UPDATE caption_bank SET classification_confidence = 0.90, classification_method = 'wave4_high_value_reclassifier' WHERE caption_id = 103 AND content_type_id = 3;

-- Caption 108: "biggest white cock...how many times he made me squirt" - Already correctly 3, VERIFY
UPDATE caption_bank SET classification_confidence = 0.90, classification_method = 'wave4_high_value_reclassifier' WHERE caption_id = 108 AND content_type_id = 3;

-- Caption 117: "JOHNNY SINS...made me squirt everywhere" - Already correctly 3, VERIFY
UPDATE caption_bank SET classification_confidence = 0.90, classification_method = 'wave4_high_value_reclassifier' WHERE caption_id = 117 AND content_type_id = 3;

-- Caption 124: "MASKED video...masturbate and SQUIRT" - Already correctly 3, VERIFY
UPDATE caption_bank SET classification_confidence = 0.90, classification_method = 'wave4_high_value_reclassifier' WHERE caption_id = 124 AND content_type_id = 3;

-- Caption 131: "BBC...a lot of squirting" - Already correctly 3, VERIFY
UPDATE caption_bank SET classification_confidence = 0.90, classification_method = 'wave4_high_value_reclassifier' WHERE caption_id = 131 AND content_type_id = 3;

-- Caption 148: "Maximo Garcia...squirting record" - Already correctly 3, VERIFY
UPDATE caption_bank SET classification_confidence = 0.90, classification_method = 'wave4_high_value_reclassifier' WHERE caption_id = 148 AND content_type_id = 3;

-- Caption 161: "CRAZY SQUIRTING video" - Already correctly 3, VERIFY
UPDATE caption_bank SET classification_confidence = 0.90, classification_method = 'wave4_high_value_reclassifier' WHERE caption_id = 161 AND content_type_id = 3;

-- Caption 212: "Squirting video" bonus - Already correctly 3, VERIFY
UPDATE caption_bank SET classification_confidence = 0.90, classification_method = 'wave4_high_value_reclassifier' WHERE caption_id = 212 AND content_type_id = 3;

-- Caption 223: "SQUIRTS all over herself like a FOUNTAIN" - Already correctly 3, VERIFY
UPDATE caption_bank SET classification_confidence = 0.90, classification_method = 'wave4_high_value_reclassifier' WHERE caption_id = 223 AND content_type_id = 3;

-- Caption 229: "new BGG 3some...SQUIRT all over" - Already correctly 3, VERIFY
UPDATE caption_bank SET classification_confidence = 0.90, classification_method = 'wave4_high_value_reclassifier' WHERE caption_id = 229 AND content_type_id = 3;

-- Caption 249: "SQUIRTING 3some" - Already correctly 3, VERIFY
UPDATE caption_bank SET classification_confidence = 0.90, classification_method = 'wave4_high_value_reclassifier' WHERE caption_id = 249 AND content_type_id = 3;

-- Caption 547: "5 girl orgy...squirting" - Already correctly 3, VERIFY
UPDATE caption_bank SET classification_confidence = 0.90, classification_method = 'wave4_high_value_reclassifier' WHERE caption_id = 547 AND content_type_id = 3;

-- Caption 549: "THREESOME...squirt all over them" - Already correctly 3, VERIFY
UPDATE caption_bank SET classification_confidence = 0.90, classification_method = 'wave4_high_value_reclassifier' WHERE caption_id = 549 AND content_type_id = 3;

-- Caption 605: "Gamer girl SQUIRTS all over his cock" - Already correctly 3, VERIFY
UPDATE caption_bank SET classification_confidence = 0.90, classification_method = 'wave4_high_value_reclassifier' WHERE caption_id = 605 AND content_type_id = 3;

-- Caption 665: "Easter Bunny squirts all over the floor" - Already correctly 3, VERIFY
UPDATE caption_bank SET classification_confidence = 0.90, classification_method = 'wave4_high_value_reclassifier' WHERE caption_id = 665 AND content_type_id = 3;

-- Caption 773: "Massive cock makes me squirt endlessly" - Already correctly 3, VERIFY
UPDATE caption_bank SET classification_confidence = 0.90, classification_method = 'wave4_high_value_reclassifier' WHERE caption_id = 773 AND content_type_id = 3;

-- Caption 779: "make her cum and SQUIRT all over" - Already correctly 3, VERIFY
UPDATE caption_bank SET classification_confidence = 0.90, classification_method = 'wave4_high_value_reclassifier' WHERE caption_id = 779 AND content_type_id = 3;

-- ============================================================================
-- CATEGORY: ANAL (1) - Anal content
-- ============================================================================

-- Caption 59: "BBC dildo...stretched my asshole" - Already correctly 1, VERIFY
UPDATE caption_bank SET classification_confidence = 0.90, classification_method = 'wave4_high_value_reclassifier' WHERE caption_id = 59 AND content_type_id = 1;

-- Caption 76: "surprise ANAL dicking" - Already correctly 1, VERIFY
UPDATE caption_bank SET classification_confidence = 0.90, classification_method = 'wave4_high_value_reclassifier' WHERE caption_id = 76 AND content_type_id = 1;

-- Caption 200: "solo video (dildo / anal / DP)" - Already correctly 1, VERIFY
UPDATE caption_bank SET classification_confidence = 0.90, classification_method = 'wave4_high_value_reclassifier' WHERE caption_id = 200 AND content_type_id = 1;

-- Caption 207: "videos include anal" - Already correctly 1, VERIFY
UPDATE caption_bank SET classification_confidence = 0.90, classification_method = 'wave4_high_value_reclassifier' WHERE caption_id = 207 AND content_type_id = 1;

-- Caption 211: "new ANAL sex video" - Already correctly 1, VERIFY
UPDATE caption_bank SET classification_confidence = 0.90, classification_method = 'wave4_high_value_reclassifier' WHERE caption_id = 211 AND content_type_id = 1;

-- Caption 529: "Step-Sister ANAL video" - Already correctly 1, VERIFY
UPDATE caption_bank SET classification_confidence = 0.90, classification_method = 'wave4_high_value_reclassifier' WHERE caption_id = 529 AND content_type_id = 1;

-- Caption 586: "SOAKED MY WHOLE BED...creampie with anal" - Already correctly 1, VERIFY
UPDATE caption_bank SET classification_confidence = 0.90, classification_method = 'wave4_high_value_reclassifier' WHERE caption_id = 586 AND content_type_id = 1;

-- Caption 588: "butt-plug...anal" - Already correctly 1, VERIFY
UPDATE caption_bank SET classification_confidence = 0.90, classification_method = 'wave4_high_value_reclassifier' WHERE caption_id = 588 AND content_type_id = 1;

-- Caption 589: "solo JOI...anal play" - mixed JOI with anal, keep as 1
UPDATE caption_bank SET classification_confidence = 0.90, classification_method = 'wave4_high_value_reclassifier' WHERE caption_id = 589 AND content_type_id = 1;

-- Caption 646: "Anal play, ass eating" - Already correctly 1, VERIFY
UPDATE caption_bank SET classification_confidence = 0.90, classification_method = 'wave4_high_value_reclassifier' WHERE caption_id = 646 AND content_type_id = 1;

-- Caption 652: "Anal creampie" - Already correctly 1, VERIFY
UPDATE caption_bank SET classification_confidence = 0.90, classification_method = 'wave4_high_value_reclassifier' WHERE caption_id = 652 AND content_type_id = 1;

-- Caption 723: "Anal, BJ, and more" - Already correctly 1, VERIFY
UPDATE caption_bank SET classification_confidence = 0.90, classification_method = 'wave4_high_value_reclassifier' WHERE caption_id = 723 AND content_type_id = 1;

-- ============================================================================
-- CATEGORY: CREAMPIE (2) - Creampie focused
-- ============================================================================

-- Caption 147: "POV blowjob...cum in my mouth" - Already correctly 2, VERIFY
UPDATE caption_bank SET classification_confidence = 0.90, classification_method = 'wave4_high_value_reclassifier' WHERE caption_id = 147 AND content_type_id = 2;

-- Caption 177: "masked sex /creampie video" - Already correctly 2, VERIFY
UPDATE caption_bank SET classification_confidence = 0.90, classification_method = 'wave4_high_value_reclassifier' WHERE caption_id = 177 AND content_type_id = 2;

-- Caption 199: "BBC video (HALF CREAMPIE)" - Already correctly 2, VERIFY
UPDATE caption_bank SET classification_confidence = 0.90, classification_method = 'wave4_high_value_reclassifier' WHERE caption_id = 199 AND content_type_id = 2;

-- Caption 202: "ends in a creampie" - Already correctly 2, VERIFY
UPDATE caption_bank SET classification_confidence = 0.90, classification_method = 'wave4_high_value_reclassifier' WHERE caption_id = 202 AND content_type_id = 2;

-- Caption 528: "cumming inside me" - creampie theme
UPDATE caption_bank SET content_type_id = 2, classification_confidence = 0.90, classification_method = 'wave4_high_value_reclassifier' WHERE caption_id = 528;

-- Caption 531: "Daddy creampie video" - Already correctly 2, VERIFY
UPDATE caption_bank SET classification_confidence = 0.90, classification_method = 'wave4_high_value_reclassifier' WHERE caption_id = 531 AND content_type_id = 2;

-- Caption 564: "creampie on ass and pussy" - Already correctly 2, VERIFY
UPDATE caption_bank SET classification_confidence = 0.90, classification_method = 'wave4_high_value_reclassifier' WHERE caption_id = 564 AND content_type_id = 2;

-- Caption 569: "creampie cum show" - Already correctly 2, VERIFY
UPDATE caption_bank SET classification_confidence = 0.90, classification_method = 'wave4_high_value_reclassifier' WHERE caption_id = 569 AND content_type_id = 2;

-- Caption 575: "CREAMPIE sex video" - Already correctly 2, VERIFY
UPDATE caption_bank SET classification_confidence = 0.90, classification_method = 'wave4_high_value_reclassifier' WHERE caption_id = 575 AND content_type_id = 2;

-- Caption 577: "Christmas creampie" - Already correctly 2, VERIFY
UPDATE caption_bank SET classification_confidence = 0.90, classification_method = 'wave4_high_value_reclassifier' WHERE caption_id = 577 AND content_type_id = 2;

-- Caption 651: "cum in my mouth" - Already correctly 2, VERIFY
UPDATE caption_bank SET classification_confidence = 0.90, classification_method = 'wave4_high_value_reclassifier' WHERE caption_id = 651 AND content_type_id = 2;

-- Caption 810: "cum in my mouth" - Already correctly 2, VERIFY
UPDATE caption_bank SET classification_confidence = 0.90, classification_method = 'wave4_high_value_reclassifier' WHERE caption_id = 810 AND content_type_id = 2;

-- Caption 819: "creampie cum and squirt show" - Already correctly 2, VERIFY
UPDATE caption_bank SET classification_confidence = 0.90, classification_method = 'wave4_high_value_reclassifier' WHERE caption_id = 819 AND content_type_id = 2;

-- ============================================================================
-- CATEGORY: LINGERIE (22) - Lingerie focused content
-- ============================================================================

-- Caption 56: "I take my bra off for you" - Already correctly 22, VERIFY
UPDATE caption_bank SET classification_confidence = 0.90, classification_method = 'wave4_high_value_reclassifier' WHERE caption_id = 56 AND content_type_id = 22;

-- Caption 109: "sexiest lingerie...slipping my panties down" - Already correctly 22, VERIFY
UPDATE caption_bank SET classification_confidence = 0.90, classification_method = 'wave4_high_value_reclassifier' WHERE caption_id = 109 AND content_type_id = 22;

-- Caption 174: "another lingerie video" - Already correctly 22, VERIFY
UPDATE caption_bank SET classification_confidence = 0.90, classification_method = 'wave4_high_value_reclassifier' WHERE caption_id = 174 AND content_type_id = 22;

-- Caption 176: "bra falls down" - Already correctly 22, VERIFY
UPDATE caption_bank SET classification_confidence = 0.90, classification_method = 'wave4_high_value_reclassifier' WHERE caption_id = 176 AND content_type_id = 22;

-- Caption 178: "shorts off (no panties)" - Already correctly 22, VERIFY
UPDATE caption_bank SET classification_confidence = 0.90, classification_method = 'wave4_high_value_reclassifier' WHERE caption_id = 178 AND content_type_id = 22;

-- Caption 205: "girl on girl content in our lingerie" - Already correctly 22, VERIFY
UPDATE caption_bank SET classification_confidence = 0.90, classification_method = 'wave4_high_value_reclassifier' WHERE caption_id = 205 AND content_type_id = 22;

-- Caption 208: "no bra side boob" - Already correctly 22, VERIFY
UPDATE caption_bank SET classification_confidence = 0.90, classification_method = 'wave4_high_value_reclassifier' WHERE caption_id = 208 AND content_type_id = 22;

-- Caption 218: "exclusive pics in the white lingerie" - Already correctly 22, VERIFY
UPDATE caption_bank SET classification_confidence = 0.90, classification_method = 'wave4_high_value_reclassifier' WHERE caption_id = 218 AND content_type_id = 22;

-- Caption 238: "sexy pics in the cutest lingerie set" - Already correctly 22, VERIFY
UPDATE caption_bank SET classification_confidence = 0.90, classification_method = 'wave4_high_value_reclassifier' WHERE caption_id = 238 AND content_type_id = 22;

-- Caption 243: "photoshoot...in lingerie" - Already correctly 22, VERIFY
UPDATE caption_bank SET classification_confidence = 0.90, classification_method = 'wave4_high_value_reclassifier' WHERE caption_id = 243 AND content_type_id = 22;

-- ============================================================================
-- CATEGORY: TOY_PLAY (17) - Dildo/vibrator focused
-- ============================================================================

-- Caption 85: "vibrator" - Already correctly 17, VERIFY
UPDATE caption_bank SET classification_confidence = 0.90, classification_method = 'wave4_high_value_reclassifier' WHERE caption_id = 85 AND content_type_id = 17;

-- Caption 226: "fucking her with a vibrator" - Already correctly 17, VERIFY
UPDATE caption_bank SET classification_confidence = 0.90, classification_method = 'wave4_high_value_reclassifier' WHERE caption_id = 226 AND content_type_id = 17;

-- Caption 532: "DP video with 2 dildos" - toy play, change from 31
UPDATE caption_bank SET content_type_id = 17, classification_confidence = 0.90, classification_method = 'wave4_high_value_reclassifier' WHERE caption_id = 532;

-- Caption 573: "HUGE DRAGON TONGUE" dildo - toy play, change from 31
UPDATE caption_bank SET content_type_id = 17, classification_confidence = 0.90, classification_method = 'wave4_high_value_reclassifier' WHERE caption_id = 573;

-- Caption 578: "full solo video outdoors...huge dildo" - Already correctly 17, VERIFY
UPDATE caption_bank SET classification_confidence = 0.90, classification_method = 'wave4_high_value_reclassifier' WHERE caption_id = 578 AND content_type_id = 17;

-- Caption 601: "girl-girl...she used my little pussy" with toys - Already correctly 17, VERIFY
UPDATE caption_bank SET classification_confidence = 0.90, classification_method = 'wave4_high_value_reclassifier' WHERE caption_id = 601 AND content_type_id = 17;

-- Caption 608: "DILDO SUCKING AND FUCKING...VIBRATOR" - Already correctly 17, VERIFY
UPDATE caption_bank SET classification_confidence = 0.90, classification_method = 'wave4_high_value_reclassifier' WHERE caption_id = 608 AND content_type_id = 17;

-- Caption 614: "slam my pussy with my favorite dildo" - Already correctly 17, VERIFY
UPDATE caption_bank SET classification_confidence = 0.90, classification_method = 'wave4_high_value_reclassifier' WHERE caption_id = 614 AND content_type_id = 17;

-- Caption 659: "BBC dildo fucking" - Already correctly 17, VERIFY
UPDATE caption_bank SET classification_confidence = 0.90, classification_method = 'wave4_high_value_reclassifier' WHERE caption_id = 659 AND content_type_id = 17;

-- Caption 703: "my toy got me soo wet" - Already correctly 17, VERIFY
UPDATE caption_bank SET classification_confidence = 0.90, classification_method = 'wave4_high_value_reclassifier' WHERE caption_id = 703 AND content_type_id = 17;

-- Caption 713: "duel vibrator dildo combo" - Already correctly 17, VERIFY
UPDATE caption_bank SET classification_confidence = 0.90, classification_method = 'wave4_high_value_reclassifier' WHERE caption_id = 713 AND content_type_id = 17;

-- Caption 750: "vibrator and fuck myself hard" - Already correctly 17, VERIFY
UPDATE caption_bank SET classification_confidence = 0.90, classification_method = 'wave4_high_value_reclassifier' WHERE caption_id = 750 AND content_type_id = 17;

-- ============================================================================
-- CATEGORY: TITS_PLAY (18) - Tits/titty focused
-- ============================================================================

-- Caption 138: "strip tease...play with my titties" - Already correctly 18, VERIFY
UPDATE caption_bank SET classification_confidence = 0.90, classification_method = 'wave4_high_value_reclassifier' WHERE caption_id = 138 AND content_type_id = 18;

-- Caption 164: "SEX SCENE with the NEW TITTIES" - Already correctly 18, VERIFY
UPDATE caption_bank SET classification_confidence = 0.90, classification_method = 'wave4_high_value_reclassifier' WHERE caption_id = 164 AND content_type_id = 18;

-- Caption 180: "soapy titties" - Already correctly 18, VERIFY
UPDATE caption_bank SET classification_confidence = 0.90, classification_method = 'wave4_high_value_reclassifier' WHERE caption_id = 180 AND content_type_id = 18;

-- Caption 540: "into my eyes?.. or my titties" - Already correctly 18, VERIFY
UPDATE caption_bank SET classification_confidence = 0.90, classification_method = 'wave4_high_value_reclassifier' WHERE caption_id = 540 AND content_type_id = 18;

-- Caption 609: "Titties bouncing in ur face" - Already correctly 18, VERIFY
UPDATE caption_bank SET classification_confidence = 0.90, classification_method = 'wave4_high_value_reclassifier' WHERE caption_id = 609 AND content_type_id = 18;

-- Caption 631: "tittyfuck + handjob...on my tits" - Already correctly 18, VERIFY
UPDATE caption_bank SET classification_confidence = 0.90, classification_method = 'wave4_high_value_reclassifier' WHERE caption_id = 631 AND content_type_id = 18;

-- Caption 643: "nipple clamps" - Already correctly 18, VERIFY
UPDATE caption_bank SET classification_confidence = 0.90, classification_method = 'wave4_high_value_reclassifier' WHERE caption_id = 643 AND content_type_id = 18;

-- Caption 685: "soapy titties and full ass" - Already correctly 18, VERIFY
UPDATE caption_bank SET classification_confidence = 0.90, classification_method = 'wave4_high_value_reclassifier' WHERE caption_id = 685 AND content_type_id = 18;

-- Caption 686: "birthday tits bundle" - Already correctly 18, VERIFY
UPDATE caption_bank SET classification_confidence = 0.90, classification_method = 'wave4_high_value_reclassifier' WHERE caption_id = 686 AND content_type_id = 18;

-- Caption 695: "huge naked tits" - Already correctly 18, VERIFY
UPDATE caption_bank SET classification_confidence = 0.90, classification_method = 'wave4_high_value_reclassifier' WHERE caption_id = 695 AND content_type_id = 18;

-- Caption 729: "titties out...Christmas special" - Already correctly 18, VERIFY
UPDATE caption_bank SET classification_confidence = 0.90, classification_method = 'wave4_high_value_reclassifier' WHERE caption_id = 729 AND content_type_id = 18;

-- ============================================================================
-- CATEGORY: PUSSY_PLAY (16) - Pussy play solo explicit
-- ============================================================================

-- Caption 555: "SPECIAL FAN BUNDLE...pussy play" - Already correctly 16, VERIFY
UPDATE caption_bank SET classification_confidence = 0.90, classification_method = 'wave4_high_value_reclassifier' WHERE caption_id = 555 AND content_type_id = 16;

-- Caption 599: "pussy play bundle" - Already correctly 16, VERIFY
UPDATE caption_bank SET classification_confidence = 0.90, classification_method = 'wave4_high_value_reclassifier' WHERE caption_id = 599 AND content_type_id = 16;

-- Caption 612: "HOTTEST SOLO VIDEO...vibrator dildo...fucked myself" - Already correctly 16, VERIFY
UPDATE caption_bank SET classification_confidence = 0.90, classification_method = 'wave4_high_value_reclassifier' WHERE caption_id = 612 AND content_type_id = 16;

-- Caption 702: "PUSSY PLAY, SEX TAPES, BLOWJOBS" - Already correctly 16, VERIFY
UPDATE caption_bank SET classification_confidence = 0.90, classification_method = 'wave4_high_value_reclassifier' WHERE caption_id = 702 AND content_type_id = 16;

-- ============================================================================
-- CATEGORY: SOLO (19) - General solo content
-- ============================================================================

-- Caption 203: "playing with my tittys and spreading my legs" - Already correctly 19, VERIFY
UPDATE caption_bank SET classification_confidence = 0.90, classification_method = 'wave4_high_value_reclassifier' WHERE caption_id = 203 AND content_type_id = 19;

-- Caption 667: "DADDY'S 1 HOUR SURPRISE...B/G, SOLO PLAY" - Already correctly 19, VERIFY
UPDATE caption_bank SET classification_confidence = 0.90, classification_method = 'wave4_high_value_reclassifier' WHERE caption_id = 667 AND content_type_id = 19;

-- Caption 689: "lace...fire pics" - Already correctly 19, VERIFY
UPDATE caption_bank SET classification_confidence = 0.90, classification_method = 'wave4_high_value_reclassifier' WHERE caption_id = 689 AND content_type_id = 19;

-- Caption 765: "solo - Daddy - Oil - Hitachi - Squirt" - Already correctly 19, VERIFY
UPDATE caption_bank SET classification_confidence = 0.90, classification_method = 'wave4_high_value_reclassifier' WHERE caption_id = 765 AND content_type_id = 19;

-- ============================================================================
-- CATEGORY: SHOWER_BATH (20) - Shower/bath themed
-- ============================================================================

-- Caption 149: "shower video i might do" - Already correctly 20, VERIFY
UPDATE caption_bank SET classification_confidence = 0.90, classification_method = 'wave4_high_value_reclassifier' WHERE caption_id = 149 AND content_type_id = 20;

-- Caption 206: "after my shower" - Already correctly 20, VERIFY
UPDATE caption_bank SET classification_confidence = 0.90, classification_method = 'wave4_high_value_reclassifier' WHERE caption_id = 206 AND content_type_id = 20;

-- Caption 219: "before my shower" - Already correctly 20, VERIFY
UPDATE caption_bank SET classification_confidence = 0.90, classification_method = 'wave4_high_value_reclassifier' WHERE caption_id = 219 AND content_type_id = 20;

-- Caption 655: "fresh out of the shower" - Already correctly 20, VERIFY
UPDATE caption_bank SET classification_confidence = 0.90, classification_method = 'wave4_high_value_reclassifier' WHERE caption_id = 655 AND content_type_id = 20;

-- ============================================================================
-- CATEGORY: POOL_OUTDOOR (21) - Pool/beach/outdoor themed
-- ============================================================================

-- Caption 140: "beach today...tan lines" - Already correctly 21, VERIFY
UPDATE caption_bank SET classification_confidence = 0.90, classification_method = 'wave4_high_value_reclassifier' WHERE caption_id = 140 AND content_type_id = 21;

-- ============================================================================
-- CATEGORY: POV (24) - POV content
-- ============================================================================

-- Caption 189: "nude POV" - Already correctly 24, VERIFY
UPDATE caption_bank SET classification_confidence = 0.90, classification_method = 'wave4_high_value_reclassifier' WHERE caption_id = 189 AND content_type_id = 24;

-- Caption 198: "POV home-made sex video" - Already correctly 24, VERIFY
UPDATE caption_bank SET classification_confidence = 0.90, classification_method = 'wave4_high_value_reclassifier' WHERE caption_id = 198 AND content_type_id = 24;

-- Caption 217: "nude POV...making my bed naked" - Already correctly 24, VERIFY
UPDATE caption_bank SET classification_confidence = 0.90, classification_method = 'wave4_high_value_reclassifier' WHERE caption_id = 217 AND content_type_id = 24;

-- Caption 247: "Halloween...POV" - Already correctly 24, VERIFY
UPDATE caption_bank SET classification_confidence = 0.90, classification_method = 'wave4_high_value_reclassifier' WHERE caption_id = 247 AND content_type_id = 24;

-- ============================================================================
-- CATEGORY: JOI (12) - Jerk off instructions
-- ============================================================================

-- Caption 720: "JOI with OIL...listen to my instructions and cum for me" - Already correctly 12, VERIFY
UPDATE caption_bank SET classification_confidence = 0.90, classification_method = 'wave4_high_value_reclassifier' WHERE caption_id = 720 AND content_type_id = 12;

-- ============================================================================
-- CATEGORY: BUNDLE_OFFER (26) - Bundle promotional
-- ============================================================================

-- Caption 126: "discounted bundle" - Already correctly 26, VERIFY
UPDATE caption_bank SET classification_confidence = 0.90, classification_method = 'wave4_high_value_reclassifier' WHERE caption_id = 126 AND content_type_id = 26;

-- Caption 132: "SPECIAL surprise...bundle" - Already correctly 26, VERIFY
UPDATE caption_bank SET classification_confidence = 0.90, classification_method = 'wave4_high_value_reclassifier' WHERE caption_id = 132 AND content_type_id = 26;

-- Caption 539: "bundle for you" - Already correctly 26, VERIFY
UPDATE caption_bank SET classification_confidence = 0.90, classification_method = 'wave4_high_value_reclassifier' WHERE caption_id = 539 AND content_type_id = 26;

-- Caption 677: "bundle of my hot pics" - Already correctly 26, VERIFY
UPDATE caption_bank SET classification_confidence = 0.90, classification_method = 'wave4_high_value_reclassifier' WHERE caption_id = 677 AND content_type_id = 26;

-- ============================================================================
-- CATEGORY: EXCLUSIVE_CONTENT (28) - Exclusive/VIP promotional
-- ============================================================================

-- Caption 215: "RED...exclusive" - Already correctly 28, VERIFY
UPDATE caption_bank SET classification_confidence = 0.90, classification_method = 'wave4_high_value_reclassifier' WHERE caption_id = 215 AND content_type_id = 28;

-- ============================================================================
-- CATEGORY: NUDE (30) - Nude content
-- ============================================================================

-- Caption 607: "nude POV after tanning" - Already correctly 30, VERIFY
UPDATE caption_bank SET classification_confidence = 0.90, classification_method = 'wave4_high_value_reclassifier' WHERE caption_id = 607 AND content_type_id = 30;

-- ============================================================================
-- CATEGORY: TEASING (31) - Generic teasing, should stay as 31 OR be reclassified
-- ============================================================================

-- Caption 3: "I took it all off for u" - teasing/strip, keep 31
UPDATE caption_bank SET classification_confidence = 0.90, classification_method = 'wave4_high_value_reclassifier' WHERE caption_id = 3 AND content_type_id = 31;

-- Caption 6: "Topless 4 U" - teasing, keep 31
UPDATE caption_bank SET classification_confidence = 0.90, classification_method = 'wave4_high_value_reclassifier' WHERE caption_id = 6 AND content_type_id = 31;

-- Caption 57: "Some videos I managed to sneak" - vague teasing, keep 31
UPDATE caption_bank SET classification_confidence = 0.90, classification_method = 'wave4_high_value_reclassifier' WHERE caption_id = 57 AND content_type_id = 31;

-- Caption 60: "gym crush...locker room...stripping" - teasing, keep 31
UPDATE caption_bank SET classification_confidence = 0.90, classification_method = 'wave4_high_value_reclassifier' WHERE caption_id = 60 AND content_type_id = 31;

-- Caption 98: "here's the full video" - generic, keep 31
UPDATE caption_bank SET classification_confidence = 0.90, classification_method = 'wave4_high_value_reclassifier' WHERE caption_id = 98 AND content_type_id = 31;

-- Caption 106: "NEW bikini...no top only bottoms" - bikini teasing, change to 21 (pool_outdoor)
UPDATE caption_bank SET content_type_id = 21, classification_confidence = 0.90, classification_method = 'wave4_high_value_reclassifier' WHERE caption_id = 106;

-- Caption 118: "MASKED sex scene" - b/g sex, change to 11
UPDATE caption_bank SET content_type_id = 11, classification_confidence = 0.90, classification_method = 'wave4_high_value_reclassifier' WHERE caption_id = 118;

-- Caption 137: "showering video" - shower, change to 20
UPDATE caption_bank SET content_type_id = 20, classification_confidence = 0.90, classification_method = 'wave4_high_value_reclassifier' WHERE caption_id = 137;

-- Caption 145: "sneak peak of me fully naked" - nude teasing, keep 31
UPDATE caption_bank SET classification_confidence = 0.90, classification_method = 'wave4_high_value_reclassifier' WHERE caption_id = 145 AND content_type_id = 31;

-- Caption 150: "VIP subscription...teasing pictures" - VIP teasing, keep 31
UPDATE caption_bank SET classification_confidence = 0.90, classification_method = 'wave4_high_value_reclassifier' WHERE caption_id = 150 AND content_type_id = 31;

-- Caption 157: "5 FULLY NUDE BODY PICTURES" - nude, change to 30
UPDATE caption_bank SET content_type_id = 30, classification_confidence = 0.90, classification_method = 'wave4_high_value_reclassifier' WHERE caption_id = 157;

-- Caption 158: "this is the full video" - generic, keep 31
UPDATE caption_bank SET classification_confidence = 0.90, classification_method = 'wave4_high_value_reclassifier' WHERE caption_id = 158 AND content_type_id = 31;

-- Caption 160: "little video to bless your Monday" - teasing, keep 31
UPDATE caption_bank SET classification_confidence = 0.90, classification_method = 'wave4_high_value_reclassifier' WHERE caption_id = 160 AND content_type_id = 31;

-- Caption 162: "Can you see my nipples?" - teasing, keep 31
UPDATE caption_bank SET classification_confidence = 0.90, classification_method = 'wave4_high_value_reclassifier' WHERE caption_id = 162 AND content_type_id = 31;

-- Caption 165: "PH scene with no blur" - generic promo, keep 31
UPDATE caption_bank SET classification_confidence = 0.90, classification_method = 'wave4_high_value_reclassifier' WHERE caption_id = 165 AND content_type_id = 31;

-- Caption 166: "pics of me and my two best friends" - teasing, keep 31
UPDATE caption_bank SET classification_confidence = 0.90, classification_method = 'wave4_high_value_reclassifier' WHERE caption_id = 166 AND content_type_id = 31;

-- Caption 168: "naughty with Butt plug" - anal toy play, change to 1
UPDATE caption_bank SET content_type_id = 1, classification_confidence = 0.90, classification_method = 'wave4_high_value_reclassifier' WHERE caption_id = 168;

-- Caption 171: "felt a little peachy today" - teasing, keep 31
UPDATE caption_bank SET classification_confidence = 0.90, classification_method = 'wave4_high_value_reclassifier' WHERE caption_id = 171 AND content_type_id = 31;

-- Caption 173: "pics & VIDEO" - generic promo, keep 31
UPDATE caption_bank SET classification_confidence = 0.90, classification_method = 'wave4_high_value_reclassifier' WHERE caption_id = 173 AND content_type_id = 31;

-- Caption 182: "bare booty of my tan lines" - teasing, keep 31
UPDATE caption_bank SET classification_confidence = 0.90, classification_method = 'wave4_high_value_reclassifier' WHERE caption_id = 182 AND content_type_id = 31;

-- Caption 184: "40 vids that I can't post" - generic bundle, change to 26
UPDATE caption_bank SET content_type_id = 26, classification_confidence = 0.90, classification_method = 'wave4_high_value_reclassifier' WHERE caption_id = 184;

-- Caption 190: "open for a surprise" - teasing, keep 31
UPDATE caption_bank SET classification_confidence = 0.90, classification_method = 'wave4_high_value_reclassifier' WHERE caption_id = 190 AND content_type_id = 31;

-- Caption 192: "50% OFF...4th of July special" - flash sale, change to 27
UPDATE caption_bank SET content_type_id = 27, classification_confidence = 0.90, classification_method = 'wave4_high_value_reclassifier' WHERE caption_id = 192;

-- Caption 209: "First one completely nude" - nude, change to 30
UPDATE caption_bank SET content_type_id = 30, classification_confidence = 0.90, classification_method = 'wave4_high_value_reclassifier' WHERE caption_id = 209;

-- Caption 220: "IM BACK!! Getting naughty and naked" - teasing, keep 31
UPDATE caption_bank SET classification_confidence = 0.90, classification_method = 'wave4_high_value_reclassifier' WHERE caption_id = 220 AND content_type_id = 31;

-- Caption 224: "Haven't sent out any nudes but BEEN hoarding them" - teasing, keep 31
UPDATE caption_bank SET classification_confidence = 0.90, classification_method = 'wave4_high_value_reclassifier' WHERE caption_id = 224 AND content_type_id = 31;

-- Caption 225: "Are u horny right now??? watch me get naked and naughty" - teasing, keep 31
UPDATE caption_bank SET classification_confidence = 0.90, classification_method = 'wave4_high_value_reclassifier' WHERE caption_id = 225 AND content_type_id = 31;

-- Caption 233: "tanning bed gets real hot" - teasing, keep 31
UPDATE caption_bank SET classification_confidence = 0.90, classification_method = 'wave4_high_value_reclassifier' WHERE caption_id = 233 AND content_type_id = 31;

-- Caption 242: "good morning...how do I look THIS good from the back" - teasing, keep 31
UPDATE caption_bank SET classification_confidence = 0.90, classification_method = 'wave4_high_value_reclassifier' WHERE caption_id = 242 AND content_type_id = 31;

-- Caption 244: "I'm laying here...naked" - teasing, keep 31
UPDATE caption_bank SET classification_confidence = 0.90, classification_method = 'wave4_high_value_reclassifier' WHERE caption_id = 244 AND content_type_id = 31;

-- Caption 542: "taking pics like this makes meeeee want to do things" - teasing, keep 31
UPDATE caption_bank SET classification_confidence = 0.90, classification_method = 'wave4_high_value_reclassifier' WHERE caption_id = 542 AND content_type_id = 31;

-- Caption 544: "YOU WON!!! OMG, BABY! YOU'RE THE WINNER" - flash sale, change to 27
UPDATE caption_bank SET content_type_id = 27, classification_confidence = 0.90, classification_method = 'wave4_high_value_reclassifier' WHERE caption_id = 544;

-- Caption 546: "rubbing my pusssyyy" - pussy play, change to 16
UPDATE caption_bank SET content_type_id = 16, classification_confidence = 0.90, classification_method = 'wave4_high_value_reclassifier' WHERE caption_id = 546;

-- Caption 553: "YOU'RE MY WINNER" - flash sale, change to 27
UPDATE caption_bank SET content_type_id = 27, classification_confidence = 0.90, classification_method = 'wave4_high_value_reclassifier' WHERE caption_id = 553;

-- Caption 556: "lick these creamy pussy and bouncy booty" - teasing, keep 31
UPDATE caption_bank SET classification_confidence = 0.90, classification_method = 'wave4_high_value_reclassifier' WHERE caption_id = 556 AND content_type_id = 31;

-- Caption 559: "pink to make the boys wink" - teasing, keep 31
UPDATE caption_bank SET classification_confidence = 0.90, classification_method = 'wave4_high_value_reclassifier' WHERE caption_id = 559 AND content_type_id = 31;

-- Caption 562: "topless tuesday" - tits play, change to 18
UPDATE caption_bank SET content_type_id = 18, classification_confidence = 0.90, classification_method = 'wave4_high_value_reclassifier' WHERE caption_id = 562;

-- Caption 571: "un-blurred PH scene" - generic, keep 31
UPDATE caption_bank SET classification_confidence = 0.90, classification_method = 'wave4_high_value_reclassifier' WHERE caption_id = 571 AND content_type_id = 31;

-- Caption 572: "watch me twerk nakey" - teasing, keep 31
UPDATE caption_bank SET classification_confidence = 0.90, classification_method = 'wave4_high_value_reclassifier' WHERE caption_id = 572 AND content_type_id = 31;

-- Caption 574: "Pink Dress video ... UNBLURRED" - generic, keep 31
UPDATE caption_bank SET classification_confidence = 0.90, classification_method = 'wave4_high_value_reclassifier' WHERE caption_id = 574 AND content_type_id = 31;

-- Caption 585: "slide out of my yellow gym shorts" - teasing, keep 31
UPDATE caption_bank SET classification_confidence = 0.90, classification_method = 'wave4_high_value_reclassifier' WHERE caption_id = 585 AND content_type_id = 31;

-- Caption 591: "TAKE OFF MY CLOTHES AND PLAY WITH MYSELF" - solo, change to 19
UPDATE caption_bank SET content_type_id = 19, classification_confidence = 0.90, classification_method = 'wave4_high_value_reclassifier' WHERE caption_id = 591;

-- Caption 594: "rub my pussy" - pussy play, change to 16
UPDATE caption_bank SET content_type_id = 16, classification_confidence = 0.90, classification_method = 'wave4_high_value_reclassifier' WHERE caption_id = 594;

-- Caption 600: "Hey baby how's your morning going" - teasing, keep 31
UPDATE caption_bank SET classification_confidence = 0.90, classification_method = 'wave4_high_value_reclassifier' WHERE caption_id = 600 AND content_type_id = 31;

-- Caption 610: "sneak peak of girl on girl content" - teasing/promo, keep 31
UPDATE caption_bank SET classification_confidence = 0.90, classification_method = 'wave4_high_value_reclassifier' WHERE caption_id = 610 AND content_type_id = 31;

-- Caption 622: "This is the video I've been telling you about" - generic, keep 31
UPDATE caption_bank SET classification_confidence = 0.90, classification_method = 'wave4_high_value_reclassifier' WHERE caption_id = 622 AND content_type_id = 31;

-- Caption 626: "nudes with this camera angle" - nude, change to 30
UPDATE caption_bank SET content_type_id = 30, classification_confidence = 0.90, classification_method = 'wave4_high_value_reclassifier' WHERE caption_id = 626;

-- Caption 629: "don't judge me for this one" - teasing, keep 31
UPDATE caption_bank SET classification_confidence = 0.90, classification_method = 'wave4_high_value_reclassifier' WHERE caption_id = 629 AND content_type_id = 31;

-- Caption 660: "DISCOUNTED COMPILATION" - bundle, change to 26
UPDATE caption_bank SET content_type_id = 26, classification_confidence = 0.90, classification_method = 'wave4_high_value_reclassifier' WHERE caption_id = 660;

-- Caption 662: "Brand new topless pics" - tits play, change to 18
UPDATE caption_bank SET content_type_id = 18, classification_confidence = 0.90, classification_method = 'wave4_high_value_reclassifier' WHERE caption_id = 662;

-- Caption 669: "The video u have been waiting for" - generic, keep 31
UPDATE caption_bank SET classification_confidence = 0.90, classification_method = 'wave4_high_value_reclassifier' WHERE caption_id = 669 AND content_type_id = 31;

-- Caption 683: "I took some new nudes" - nude, change to 30
UPDATE caption_bank SET content_type_id = 30, classification_confidence = 0.90, classification_method = 'wave4_high_value_reclassifier' WHERE caption_id = 683;

-- Caption 697: "50% OFF Isabella FULL Facial Cum Show" - flash sale, change to 27
UPDATE caption_bank SET content_type_id = 27, classification_confidence = 0.90, classification_method = 'wave4_high_value_reclassifier' WHERE caption_id = 697;

-- Caption 698: "i think i need a bikini top that actually fits me" - teasing, keep 31
UPDATE caption_bank SET classification_confidence = 0.90, classification_method = 'wave4_high_value_reclassifier' WHERE caption_id = 698 AND content_type_id = 31;

-- Caption 707: "my tits looking good here" - tits play, change to 18
UPDATE caption_bank SET content_type_id = 18, classification_confidence = 0.90, classification_method = 'wave4_high_value_reclassifier' WHERE caption_id = 707;

-- Caption 717: "Wanna see what I'm doing right now" - teasing, keep 31
UPDATE caption_bank SET classification_confidence = 0.90, classification_method = 'wave4_high_value_reclassifier' WHERE caption_id = 717 AND content_type_id = 31;

-- Caption 755: "got my pussy all messy for daddy" - pussy play, change to 16
UPDATE caption_bank SET content_type_id = 16, classification_confidence = 0.90, classification_method = 'wave4_high_value_reclassifier' WHERE caption_id = 755;

-- Caption 766: "I have something I really want you to see" - teasing, keep 31
UPDATE caption_bank SET classification_confidence = 0.90, classification_method = 'wave4_high_value_reclassifier' WHERE caption_id = 766 AND content_type_id = 31;

-- Caption 784: "your girls in the kitchen cooking like this" - teasing, keep 31
UPDATE caption_bank SET classification_confidence = 0.90, classification_method = 'wave4_high_value_reclassifier' WHERE caption_id = 784 AND content_type_id = 31;

-- ============================================================================
-- Verify all updates and commit
-- ============================================================================

COMMIT;

-- ============================================================================
-- VERIFICATION QUERY - Run after executing updates
-- ============================================================================
-- SELECT content_type_id, COUNT(*) as count,
--        AVG(classification_confidence) as avg_confidence
-- FROM caption_bank
-- WHERE classification_method = 'wave4_high_value_reclassifier'
-- GROUP BY content_type_id
-- ORDER BY count DESC;

"""Template library for the AI Creative Studio (fallback generator content).

Everything a creator can say about the product is injected from verified fact IDs ({N_SWEET} ...) that
`cip.studio` resolves from data/raw/ads.csv. Nothing here states a product fact directly. Anything not
in the supplied files is a [[CONFIRM: ...]] placeholder. Script lines are Hinglish (Roman script), as in
the creators' own transcripts, and need native-speaker review before shooting.
"""
from __future__ import annotations

# ---------------------------------------------------------------- product fact specs
# (fact_id, regex that must match a claims_made value in that product's ads, role)
PRODUCTS = {
    "Nutrimix": {
        "name": "Little Joys Nutrimix",
        "ad_regex": r"Nutrimix",
        "facts": [
            ("N_SWEET", r"^Sweetened with jaggery and dates$", "sweetener"),
            ("N_INGR", r"^Contains ragi, bajra, almonds, and walnuts$", "ingredients"),
            ("N_NOARTSW", r"^No artificial sweeteners$", "sweetener"),
            ("N_VITMIN", r"^Contains 23 vitamins and minerals$", "composition"),
        ],
        "placeholders": ["variant / age band", "serving size and how to mix", "flavour", "price / offer"],
    },
    "Proteinmix": {
        "name": "Little Joys Proteinmix",
        "ad_regex": r"Proteinmix",
        "facts": [
            ("P_PROT", r"^12g protein per scoop$", "protein"),
            ("P_PLANT", r"^100% plant protein$", "source"),
            ("P_SOURCES", r"^Plant-based protein made with soy, pea, and brown rice isolate$", "source"),
            ("P_SUGAR", r"^No added sugar, no preservatives$", "sugar"),
            ("P_NOTASTE", r"^No taste change, no smell$", "taste"),
            ("P_MEALS", r"^Can be mixed into regular meals like roti, dosa, chilla, and pancakes$", "usage"),
        ],
        "placeholders": ["age suitability / serving guidance", "price / offer", "allergen statement (soy)"],
    },
}

# Claim patterns found in the ad files that must NOT be reused (unsubstantiated, comparative or health-benefit).
RESTRICTED_AD_PATTERNS = [
    (r"immun", "Immunity claim", "No evidence in the supplied files; health-benefit claim."),
    (r"\bboost", "'Boost' claim", "Implied benefit claim; not substantiated in the files."),
    (r"\bonly\b|\bbest\b|bestseller|#1|no\.? ?1", "Superlative / exclusivity", "Needs documentary substantiation."),
    (r"\d(?:\.\d)?\s?x\b", "Multiplier comparison (e.g. 2.5X)", "Comparative claim; baseline unknown."),
    (r"lakh|million|loved by", "Popularity claim", "Number not verifiable from the files."),
    (r"\blab\b|lab[- ]tested|eurofins|third.party|lab report", "Third-party testing claim", "Certificates are not in the supplied files."),
    (r"growth|height|taller|weight|brain|iq\b|memory", "Growth / development claim", "Health outcome; not substantiated."),
    (r"stomach|gentle|digest|gut", "Digestive / gentleness claim", "Health claim; not substantiated."),
    (r"10/10|10 out of 10", "Rating claim", "Source unknown."),
    (r"finish milk|two minutes", "Behavioural outcome claim", "Outcome claim; not substantiated."),
    (r"complete physical health|complete nutrition", "'Complete' nutrition claim", "Overbroad claim."),
]

# ---------------------------------------------------------------- global avoid rules (id, text, reason)
GLOBAL_AVOID = [
    ("health", "Any claim that the product treats, prevents or cures anything, or improves immunity, growth, height, weight, brain development or strength.",
     "No such claim is verified in the supplied files; several older ads contain them (see restricted claims list)."),
    ("numbers", "Any number, percentage, multiplier or vitamin count that is not one of the verified product facts for the chosen product.",
     "Numeric claims must trace to a fact ID."),
    ("superlative", "Superlatives and exclusivity (\"best\", \"only\", \"No. 1\", \"bestseller\", \"loved by 10 lakh moms\").",
     "Appear in older ad copy but cannot be substantiated from the files."),
    ("compare", "Comparisons with, or mentions of, other brands or products.",
     "Competitor kids-nutrition brands appear in several shortlisted creators' sponsored posts; keep the Little Joys video clean of them."),
    ("lab", "Third-party testing or certification claims (e.g. lab tested, Eurofins).",
     "Mentioned in ad copy, but certificates are not part of the supplied files."),
    ("outcome", "Scripted taste or eating outcomes (\"kids love it\", \"finishes it in two minutes\"). Film real reactions only.",
     "Outcome claims are unverified; scripted reactions would misrepresent what happened."),
    ("endorse", "\"Doctor recommended\", \"expert approved\" or any medical-authority endorsement the creator has not personally confirmed.",
     "Endorsement must be genuine and disclosed."),
    ("age", "Age suitability, serving size or dosage statements unless supplied by Little Joys.",
     "Not available in the supplied files; left as [[CONFIRM: ...]] placeholders."),
    ("disclosure", "Omitting the paid-partnership disclosure.",
     "Every script ends with a disclosure line; confirm the platform's disclosure label."),
]

# ---------------------------------------------------------------- creator archetypes
CREATORS = {
    "CR-03": dict(
        product="Nutrimix", archetype="Calm clinic consult (label walk-through)", pace=2.3,
        durations=[5, 8, 11, 11, 8],
        post_evidence=["DY9ulQhz-tg", "Dci4UAFTkdA", "DdROq2BT18G", "DXWtrJdkaqc"],
        dna_features=["explainer_to_camera", "child_present"],
        concepts=[
            ("Label Walk-Through, Clinic Style",
             "A calm, structured segment in the creator's usual professional setting: three things to check on a kids' mix label, "
             "then the Little Joys Nutrimix label read aloud line by line. He quotes what the pack states and nothing else; no health promises."),
            ("Myth vs Label",
             "Opens like his myth-busting posts (a common parental assumption), then settles it by reading the pack's own ingredients list. "
             "The product appears as the example being checked, not as a health fix or a recommendation."),
        ],
        hooks=[
            ("question", "Bacche ke doodh mein kya mila rahe hain? Label padha hai?", "LABEL PADHA?", "DY9ulQhz-tg"),
            ("myth", "Myth: pack ke front par jo likha hai, wahi poori kahani hai. Chaliye check karte hain.", "MYTH vs LABEL", "Dci4UAFTkdA"),
            ("list", "Koi bhi mix kharidne se pehle yeh teen cheezein dekhiye.", "3 CHEEZEIN", "DXWtrJdkaqc"),
            ("fear", "Parents ki sabse badi confusion: label ka matlab kya hota hai?", "LABEL KA MATLAB", "DdROq2BT18G"),
            ("direct", "Ek minute dijiye, main bataata hoon label kaise padhte hain.", "LABEL KAISE PADHEIN", "DY9ulQhz-tg"),
            ("habit", "Jo aap roz bacche ko dete hain, uski ingredients list aapne kitni baar padhi hai?", "INGREDIENTS LIST", "DY9ulQhz-tg"),
        ],
        voice=[  # slots 2-4 (index 0..2), two options each
            ["Har pack ka daava alag hota hai. Main front ke daave nahi, back ki list dekhta hoon.",
             "Pehla rule: front ka slogan nahi, back ki ingredients list padhiye. Wahi sabse seedhi jaankari hoti hai."],
            ["Little Joys Nutrimix ki list mein likha hai: \"{N_INGR}\". Sweetener ke baare mein: \"{N_SWEET}\".",
             "Is Nutrimix ke label par: \"{N_SWEET}\" aur \"{N_NOARTSW}\". Ingredients: \"{N_INGR}\"."],
            ["Teen cheezein dekhiye: ingredients, sweetener, aur umar ke liye guidance. [[CONFIRM: age band and serving guidance]]",
             "Kitna aur kab, yeh apne pediatrician se poochiye. [[CONFIRM: serving guidance from Little Joys]]"],
        ],
        visual=[
            ["Medium close-up, creator in his usual professional attire (stethoscope, as in his posts), calm direct address; jar held low, label not yet shown.",
             "Clinic desk with a notepad beside the jar; creator looks up from his notes to camera and asks the question."],
            ["Same framing; a text card slides in: front of pack vs ingredients list. Slow push-in, no energetic transitions.",
             "Cut to the jar flipped round: back panel fills the frame, creator's finger on the ingredients heading."],
            ["Macro shot of the real label; each quoted line is highlighted as he reads it (highlight just the pack's own words). Cut-aways of him nodding.",
             "Split frame: label panel left, creator right; each quoted line appears as a lower-third as it is read."],
            ["Back to medium close-up; he counts the three checks on his fingers with matching list overlays (list-based style from his posts).",
             "Notepad shot: he ticks the three checks as he says them, then returns to face for the last line."],
            ["Creator holds the jar beside his face, steady shot, calm expression; end card with link/code placeholder and the disclosure tag.",
             "Desk shot, jar and notepad; creator closes with a calm nod; end card with link/code placeholder and disclosure tag."],
        ],
        text=[
            ["Front of pack vs ingredients list", "Check the list, not the slogan"],
            ["\"{N_INGR}\"", "\"{N_SWEET}\""],
            ["Ingredients | Sweetener | [[CONFIRM: age and serving guidance]]", "Ask your paediatrician about serving"],
        ],
        ctas=[
            dict(kind="label_link", spoken="Label khud padhiye. Link: [[CONFIRM: link or code]]. Little Joys ke saath paid partnership.",
                 on_screen="Read the full label: [[CONFIRM: link or code]]  #ad", note="Soft, information-led CTA that fits a consult-style creator."),
            dict(kind="share", spoken="Kisi parent ke kaam aaye toh share kijiye. Link: [[CONFIRM: link]]. Paid partnership.",
                 on_screen="Share with a parent  |  [[CONFIRM: link]]  #ad", note="Uses the 'SHARE' on-screen pattern seen in his posts."),
        ],
        caption="Label padhna seekhiye: ingredients, sweetener, serving. Little Joys Nutrimix ke label par jo likha hai, wahi dikhaya hai. "
                "[[CONFIRM: age and serving guidance]]  #ad #paidpartnership [[CONFIRM: brand handle to tag]]",
        tone=dict(
            summary="Calm, measured and reassuring: a clinician explaining something to a parent, not selling to them.",
            delivery=["Pace: slow and even; pause after each quoted label line.",
                      "Language: Hindi with English terms; list-based ('teen cheezein') structure.",
                      "On camera in his usual professional setting; no influencer-style transitions or slang.",
                      "Read label lines verbatim; do not paraphrase them into benefits."],
            language="Hindi + English (as in his posts)", camera="Piece to camera, clinic setting"),
        creator_avoid=["Energetic transitions, casual slang or a sales-pitch register (the creator's own profile flags these as out of place).",
                       "Linking the product to any of the medical topics he normally covers (fever, posture, screen time)."],
    ),
    "CR-11": dict(
        product="Nutrimix", archetype="Family day-in-the-life vlog (voiceover montage)", pace=2.6,
        durations=[5, 8, 10, 9, 6],
        post_evidence=["DbDqQdxSETg", "DZZx2TaSua5", "DZxA-yUy39B", "DeMkb_KSRFj"],
        dna_features=["lifestyle_routine", "child_present"],
        concepts=[
            ("Doodh Time: A Day in Our Ghar",
             "One episode of his daily-vlog series where Little Joys Nutrimix simply shows up in the morning milk routine. "
             "Starts with a candid family moment, mentions the product once with its label line, and keeps the child's reaction real."),
            ("The Doodh Drama",
             "A short story arc built around an everyday argument at milk time, told in his 'chalo batata hoon' voice. "
             "The product is part of the routine, not the punchline; no scripted verdict."),
        ],
        hooks=[
            ("story", "Guys, aaj subah doodh ke time pe ghar mein itna drama hua. Chalo batata hoon kya hua.", "AAJ KA DRAMA", "DbDqQdxSETg"),
            ("series", "Day [[CONFIRM: day number of the vlog series]]. Aur aaj bacche ne ek naya rule bana diya.", "DAY __", "DZZx2TaSua5"),
            ("kid", "Papa, aaj main doodh ki boss hoon!", "DOODH KI BOSS", "DZxA-yUy39B"),
            ("cliff", "Subah uthte hi ek hi sawaal: aaj doodh kaun banayega?", "DOODH KAUN BANAYEGA?", "DbDqQdxSETg"),
            ("laugh", "Yeh dekho, doodh ka glass kahan chhupa diya gaya!", "GLASS KAHAN?", "DeMkb_KSRFj"),
            ("sound", "Humare ghar ki subah ki awaaz suniye. Yeh roz ka hai.", "SUBAH KI AWAAZ", "DZ4z7cCS-VO"),
        ],
        voice=[
            ["Subah uthte hi sabse pehle bacche ka doodh, yeh humare ghar ka routine hai. Aur roz ki tarah thoda naatak bhi.",
             "Humare ghar ki subah sabse busy hoti hai: school ki tayyari, bag, aur doodh ka glass."],
            ["Aaj humne usme Little Joys Nutrimix mila ke dekha. Pack par likha hai: \"{N_SWEET}\". Maine khud padha, aap bhi dekh lijiye.",
             "Mummy ne Little Joys Nutrimix mix kiya. Pack par \"{N_INGR}\" likha hai. Hum bas try kar rahe hain."],
            ["Bacche ka reaction aap khud dekh lijiye. Maine kuch bolne ko nahi kaha.",
             "Reaction jaisa tha, waisa hi dikha raha hoon. Koi daava nahi, bas hamara routine."],
        ],
        visual=[
            ["Handheld phone shot in warm morning light; the child is already in frame near the milk glass; creator talks to camera mid-motion (high-energy transitions, as in his vlogs).",
             "Quick montage: slippers, bedhead, glass on the kitchen counter; voiceover over the montage and a Day card on screen."],
            ["Voiceover montage: bed, brushing teeth, school bag; fast cuts, natural sound kept in.",
             "Wide kitchen shot with family moving around; unscripted laughter stays in the edit."],
            ["One continuous handheld shot of the Nutrimix being mixed into milk; pack label held to camera for 2 seconds so the quoted line is legible.",
             "Close on the pack in hand, then the stirring; natural indoor light, no studio product-hero shot."],
            ["Child's candid reaction filmed handheld; do not re-take for a 'perfect' reaction.",
             "Child goes about the morning with the glass nearby; creator laughs off-camera."],
            ["Family at the table, creator waves to camera; end card with link/code placeholder and disclosure.",
             "Creator and child wave bye from the doorway; end card with link/code placeholder and disclosure."],
        ],
        text=[
            ["Subah ka routine", "Humare ghar ki subah"],
            ["\"{N_SWEET}\"", "\"{N_INGR}\""],
            ["Reaction: bilkul asli", "Jo hua, wahi dikhaya"],
        ],
        ctas=[
            dict(kind="link", spoken="Agar aapke ghar mein bhi doodh ka yahi drama hota hai, toh details link mein hain: [[CONFIRM: link, code or offer]]. Little Joys ke saath paid partnership.",
                 on_screen="Details in link  |  [[CONFIRM: code or offer]]  #ad", note="Casual vlog-style CTA; offer is a placeholder."),
            dict(kind="series", spoken="Aap bhi try karna chahein toh link bio mein hai: [[CONFIRM: link]]. Kal ke vlog mein milte hain. Paid partnership.",
                 on_screen="Kal milte hain  |  [[CONFIRM: link]]  #ad", note="Ties the CTA to the next episode of his series."),
        ],
        caption="Doodh time ka hamara routine. Pack par jo likha hai, woh video mein dikhaya hai. [[CONFIRM: variant and age band]]  "
                "#ad #paidpartnership [[CONFIRM: brand handle to tag]]",
        tone=dict(
            summary="Warm, upbeat and conversational: a dad narrating a real morning, with the product as a passing detail.",
            delivery=["Pace: brisk with natural pauses; keep the 'Guys, chalo batata hoon' opener from his sponsored posts.",
                      "Language: Hindi, English only for the product name.",
                      "Candid, unscripted family moments; leave imperfect takes in.",
                      "One product mention with one label line; no formal claims."],
            language="Hindi", camera="Handheld vlog, family in frame"),
        creator_avoid=["Studio lighting, formal scripted product claims or a frame without family (flagged as foreign to his style).",
                       "Any competitor brand: his earlier sponsored posts feature other kids-nutrition brands; confirm exclusivity before shooting.",
                       "Scripting the child's reaction or a taste verdict."],
    ),
    "CR-02": dict(
        product="Proteinmix", archetype="Multi-character domestic skit", pace=2.8,
        durations=[4, 9, 12, 9, 6],
        post_evidence=["Dc1GoRgN9re", "DctTcNQtUqC", "Dd35jNPsU6q", "Db0zjyAMOpT"],
        dna_features=["skit", "storytelling", "humour"],
        concepts=[
            ("Mummy's Secret Ingredient",
             "A short family skit in her own kitchen: a suspicious son and father try to work out what changed in the roti. "
             "Mummy confesses to the camera, reads the pack's own usage line, and the skit ends on a joke, not a product verdict."),
            ("Ghar Ka Jaasoos",
             "The household detective gag: the youngest 'investigates' what is in dinner. Premise lands in the first-frame text overlay, "
             "as in her skits, and the product appears as a plain-spoken reveal with its label lines."),
        ],
        hooks=[
            ("premise", "BETA: Mummy, roti mein kuch alag hai na?", "Mummy ka secret ingredient", "Dc1GoRgN9re"),
            ("whisper", "MUMMY (camera ki taraf): Shh! Papa ko mat batana, aaj roti mein kya gaya hai.", "SHH... SECRET", "Db0zjyAMOpT"),
            ("detective", "BETA: Ghar ka sabse chhota jaasoos phir shuru ho gaya.", "Ghar ka jaasoos", "DctTcNQtUqC"),
            ("sentiment", "MUMMY: Mummy ka bhi toh ek secret hota hai.", "Mummy ka secret", "Dd35jNPsU6q"),
            ("domestic", "MUMMY: Ek hi roti, teen sawaal. Roz ka drama.", "Ek roti, teen sawaal", "DctTcNQtUqC"),
            ("confession", "MUMMY: Ek baat kabool karti hoon. Maine roti mein kuch milaya hai.", "KABOOL KARTI HOON", "Db0zjyAMOpT"),
        ],
        voice=[
            ["BETA: Mummy, roti ka rang thoda alag lag raha hai. MUMMY: Rang? Woh toh naya aata hai. BETA: Jaasoos ki nazar se kuch nahi chhupta!",
             "PAPA: Tum dono kuch chhupa rahe ho. MUMMY: Bilkul nahi! PAPA: Roti ko ghoor kar dekh raha hoon, samajh jaunga."],
            ["MUMMY (camera ko): Theek hai, bata deti hoon. Little Joys Proteinmix, bas ek scoop atta mein. Pack par likha hai: \"{P_MEALS}\". Aur \"{P_NOTASTE}\".",
             "MUMMY: Ruko, bata deti hoon. Yeh Little Joys Proteinmix hai. Pack ke hisaab se: \"{P_MEALS}\". Aur \"{P_NOTASTE}\"."],
            ["BETA (chabate hue): Phir bhi mujhe shak hai. PAPA: Mujhe bhi. MUMMY: Kal phir check kar lena.",
             "BETA: Main toh kal phir jaanch karunga. PAPA: Main bhi saath hoon. MUMMY: Dono jaasoos, ek roti."],
        ],
        visual=[
            ["Her own kitchen; premise text overlay on the very first frame; Kripa as BETA peeks at camera with an exaggerated suspicious look.",
             "Mummy glances over her shoulder, whispering to camera while rolling dough; premise overlay on the first frame."],
            ["Rapid character switch BETA / PAPA / MUMMY with quick cuts at the same table; expressive reactions.",
             "Split-screen of two characters across the table, quick back-and-forth."],
            ["Mummy breaks the fourth wall and holds the Little Joys Proteinmix pack beside the dough; label legible for 2 seconds.",
             "Close on a hand adding one scoop to atta dough with the pack beside the bowl; cut back to Mummy's confession."],
            ["Reaction shots: BETA chewing deadpan, PAPA squinting; comic beat, then a freeze-frame.",
             "BETA slides the plate over with a raised eyebrow; Papa shrugs."],
            ["Mummy winks to camera; end card with link/code placeholder and disclosure.",
             "Family freeze-frame at the table; end card with link/code placeholder and disclosure."],
        ],
        text=[
            ["BETA: jaasoos mode ON", "Ghar ka jaasoos"],
            ["{P_PROT}", "{P_NOTASTE}"],
            ["Shak abhi bhi hai", "Kal phir check karenge"],
        ],
        ctas=[
            dict(kind="comment", spoken="Aapke ghar mein jaasoos kaun hai? Comment mein batao. Details link mein: [[CONFIRM: link, code or offer]]. Little Joys ke saath paid partnership.",
                 on_screen="Kaun hai aapke ghar ka jaasoos?  |  [[CONFIRM: link]]  #ad", note="Comment prompt keeps the skit's playful tone."),
            dict(kind="link", spoken="Aap bhi apne ghar ke jaasoos ko try karwana chahein toh link: [[CONFIRM: link or code]]. Paid partnership with Little Joys.",
                 on_screen="Link: [[CONFIRM: link or code]]  #ad", note="Plain link CTA after the joke lands."),
        ],
        caption="Ghar ka jaasoos phir shuru. Roti mein kya tha? Pack par jo likha hai woh video mein hai. [[CONFIRM: age suitability and serving guidance]]  "
                "#ad #paidpartnership [[CONFIRM: brand handle to tag]]",
        tone=dict(
            summary="Playful, expressive and relatable: comic exaggeration for the skit, a sincere plain-spoken beat for the product reveal.",
            delivery=["Pace: fast in the skit, slower and clear on the product lines.",
                      "Language: English + Hindi mix, as in her posts.",
                      "Rapid character switching and text-overlay premise on the first frame.",
                      "The product is the 'secret' of a small domestic annoyance, never a lecture."],
            language="Hindi + English mix", camera="Domestic set, character switching"),
        creator_avoid=["Studio lighting, corporate jargon or a placement that ignores the domestic setting (her profile flags these as foreign).",
                       "Any joke that implies the food is hidden from the family unsafely or that the child 'must' eat it; keep the gag light and obviously staged.",
                       "Scripted claims about taste beyond the pack's own line; her sponsored track record is empty, so confirm disclosure habits."],
    ),
    "CR-05": dict(
        product="Nutrimix", archetype="Child-performer bargaining sketch with adult co-star", pace=2.4,
        durations=[4, 8, 11, 10, 6],
        post_evidence=["DOcov2NibmL", "DeJWZvINVGK", "DczvRVxJkPq", "DKHKkopvg9W"],
        dna_features=["child_present", "humour"],
        concepts=[
            ("Doodh Ki Shart",
             "A short bargaining sketch in the child's own style: she sets a 'condition' for milk, the adult produces the Little Joys Nutrimix as a prop, "
             "and an adult voiceover (not the child) reads one label line. She ends on a playful 'verdict tomorrow'."),
            ("Ek Serious Baat",
             "She opens with a mock-serious announcement to camera, exactly like her everyday-problem posts, and the product is just what Mummy brings to the table. "
             "No product claims come from the child."),
        ],
        hooks=[
            ("serious", "Mummy! Aaj main doodh ke baare mein ek bahut serious baat karungi.", "SERIOUS BAAT", "DOcov2NibmL"),
            ("bargain", "Doodh piyungi, lekin meri ek shart hai!", "MERI SHART", "DOcov2NibmL"),
            ("question", "Aap bataiye, kya doodh sirf safed hona chahiye?", "DOODH KA COLOUR?", "DKHKkopvg9W"),
            ("costume", "Aaj ka outfit ready hai, bas doodh ka glass baaki hai.", "OUTFIT READY", "DczvRVxJkPq"),
            ("camera", "Pehle acche se batao, doodh kaise piyun, aise ya aise?", "AISE YA AISE?", "DeJWZvINVGK"),
            ("secret", "Mummy aur Papa ko ek raaz batati hoon.", "EK RAAZ", "DdgmFHRpgDb"),
        ],
        voice=[
            ["SIA (haath nachate hue): Doodh mein kuch toh mazedaar chahiye, tab hi soch rahi hoon. MUMMY: Achha? Kya shart hai?",
             "MUMMY: Doodh piyo. SIA: Pehle meri shart suno, Mummy. Offer do mujhe!"],
            ["MUMMY: Chalo, aaj Little Joys Nutrimix daal ke dekhte hain. SIA: Yeh kya hai? Dikhao! VOICEOVER (adult): Pack par likha hai: \"{N_INGR}\".",
             "MUMMY: Yeh dekho, Little Joys Nutrimix. SIA: Mujhe bhi chammach dena! VOICEOVER (adult): Pack par likha hai: \"{N_SWEET}\"."],
            ["SIA (dramatic pause): Hmm... Main apna verdict kal doongi, Mummy.",
             "SIA (aankhein bandh karke): Aaj suspense rehne do. Kal batati hoon."],
        ],
        visual=[
            ["Child at home in a bright room, close to camera, exaggerated serious face; adult off-camera.",
             "Child sits with arms crossed at the table; an adult hand places a glass of milk into frame."],
            ["Child bargaining with big hand gestures; quick punch-in cuts for comic timing with the adult co-star.",
             "Two-shot of child and adult trading lines; the adult stays mostly off-camera."],
            ["An adult hand shows the Little Joys Nutrimix pack as a prop; the child inspects it with exaggerated curiosity; adult voiceover reads the label line over a close shot of the pack.",
             "Child picks up a spoon and looks at the pack; adult voiceover reads the label line over the label close-up."],
            ["Child's dramatic thinking pause, slow push-in, then a playful 'verdict tomorrow' shrug.",
             "Child holds the glass with both hands, eyes to camera, teasing a verdict for tomorrow."],
            ["Child waves to camera; end card with link/code placeholder; an adult voice delivers the disclosure.",
             "Mummy and child wave together; end card with link/code placeholder and disclosure."],
        ],
        text=[
            ["MERI SHART", "Doodh ka negotiation"],
            ["\"{N_INGR}\"", "\"{N_SWEET}\""],
            ["Verdict: kal!", "Suspense..."],
        ],
        ctas=[
            dict(kind="link", spoken="VOICEOVER (adult): Details Little Joys ke link par: [[CONFIRM: link or code]]. Yeh paid partnership hai. SIA: Bye bye!",
                 on_screen="Link: [[CONFIRM: link or code]]  #ad", note="An adult delivers the CTA and disclosure; the child only signs off."),
            dict(kind="follow", spoken="SIA: Kal ka verdict dekhna mat bhoolna! VOICEOVER (adult): Details: [[CONFIRM: link]]. Paid partnership with Little Joys.",
                 on_screen="Kal ka verdict  |  [[CONFIRM: link]]  #ad", note="Cliffhanger CTA; requires a follow-up post to be planned."),
        ],
        caption="Doodh ki shart pe aaj ka sketch. Pack par jo likha hai woh video mein hai. [[CONFIRM: variant and age band]]  "
                "#ad #paidpartnership [[CONFIRM: brand handle to tag]]",
        tone=dict(
            summary="High-energy, playful child performance with an adult straight-man; product facts come only from an adult voiceover.",
            delivery=["Pace: quick and bouncy for the child, slow and clear for the adult label line.",
                      "Language: Hindi, matching her posts.",
                      "Short, scripted-by-adults lines in her own comedic-timing style; exaggerated expressions.",
                      "Product is a prop in an everyday home situation, not a testimonial."],
            language="Hindi", camera="Home set, child to camera with adult co-star"),
        creator_avoid=["A polished testimonial in which the child reads product benefits or specifications (her profile flags this as foreign, and it is a child-advertising risk).",
                       "Having the child make any claim, comparison or taste verdict about the product; keep the verdict a joke.",
                       "Competitor brands: her sponsored posts have shown other kids-nutrition brands.",
                       "Filming or publishing without the guardians' confirmation of consent and disclosure."],
    ),
    "CR-01": dict(
        product="Proteinmix", archetype="Doctor label-check (split-screen)", pace=2.7,
        durations=[4, 9, 12, 9, 6],
        post_evidence=["DZKvlfmIxR-", "DYpMEvmzwch", "Ddd9hGsoZ3V", "DaSmKPaId-3"],
        dna_features=["explainer_to_camera", "child_present"],
        concepts=[
            ("Label Check: Protein Mix",
             "A split-screen label walk-through in her clinical setting, in the style of her packaged-product review posts. "
             "She reads the Little Joys Proteinmix label lines as printed, and sends parents back to their child's doctor for serving questions."),
            ("Front vs Back of Pack",
             "She contrasts the front-of-pack slogan with the back-of-pack facts and uses the Proteinmix label as the worked example. "
             "She endorses reading labels, not the product; any endorsement needs her own confirmation."),
        ],
        hooks=[
            ("label", "Protein powder ka label kaise padhein? Ek minute se kam mein samjhiye.", "LABEL KAISE PADHEIN", "DZKvlfmIxR-"),
            ("alert", "LABEL CHECK: aaj ek protein mix ka label padhte hain.", "LABEL CHECK", "DZKvlfmIxR-"),
            ("question", "Kya aapne kabhi bacche ke supplement ka poora label padha hai?", "POORA LABEL PADHA?", "Ddd9hGsoZ3V"),
            ("mistake", "Label padhte waqt parents yeh ek galti karte hain: sirf front dekhte hain.", "EK GALTI", "Ddd9hGsoZ3V"),
            ("compare", "Front of pack aur back of pack. Fark samjhiye.", "FRONT vs BACK", "DYpMEvmzwch"),
            ("save", "Yeh reel save kar lijiye. Label padhna yaad rahega.", "SAVE THIS REEL", "DZKvlfmIxR-"),
        ],
        voice=[
            ["Pehla rule: front par likhe daave nahi, back ki ingredients list aur serving table dekhiye.",
             "Do cheezein dekhiye: ingredients ki list aur serving size. Baaki cheezein uske baad."],
            ["Little Joys Proteinmix ka label: \"{P_PROT}\". Source ke baare mein: \"{P_SOURCES}\". Aur: \"{P_SUGAR}\".",
             "Ab label dekhiye. \"{P_SOURCES}\". \"{P_PROT}\". Aur sugar ke baare mein likha hai: \"{P_SUGAR}\"."],
            ["Kisi bhi supplement se pehle apne bacche ke doctor se baat zaroor kijiye. Pack par age guidance: [[CONFIRM: age band and serving guidance from Little Joys]]",
             "Kitna dena hai aur kab, yeh doctor se confirm kijiye. Pack ki guidance: [[CONFIRM: age and serving guidance from Little Joys]]"],
        ],
        visual=[
            ["Split-screen: left, doctor to camera in her clinic; right, jar front-of-pack. Medical doll visible on the desk (from her posts).",
             "Doctor holds the jar up to camera, then flips it to the back panel."],
            ["Split-screen: front-of-pack vs back-of-pack panels with arrow overlays.",
             "Doctor taps a desk whiteboard with two headings: Ingredients | Serving size."],
            ["Split-screen: label panel left, doctor reading right; each quoted line is highlighted as she reads it, nothing more.",
             "Full-frame label macro with a line-by-line highlight; doctor voiceover."],
            ["Back to doctor, clinic background, calm; on-screen card shows the confirm placeholders.",
             "Doctor gestures to the medical doll while she says to ask the child's doctor."],
            ["Doctor points to the 'Save' icon on screen; end card with link/code placeholder and disclosure.",
             "Doctor closes with a nod; end card with link/code placeholder and disclosure."],
        ],
        text=[
            ["Front of pack vs back of pack", "Ingredients | Serving size"],
            ["\"{P_PROT}\"", "\"{P_SOURCES}\""],
            ["Age and serving: [[CONFIRM: from Little Joys]]", "Ask your child's doctor first"],
        ],
        ctas=[
            dict(kind="save", spoken="Save this reel taaki label padhna yaad rahe. Product details: [[CONFIRM: link or code]]. Little Joys ke saath paid partnership.",
                 on_screen="Save this reel  |  [[CONFIRM: link]]  #ad", note="Uses her signature 'Save this reel' call to action."),
            dict(kind="link", spoken="Poora label Little Joys ki details par dekh sakte hain: [[CONFIRM: link or code]]. Yeh paid partnership hai.",
                 on_screen="Full label: [[CONFIRM: link or code]]  #ad", note="Information-led CTA."),
        ],
        caption="Label padhna seekhiye: protein mix ka label, front vs back. Little Joys Proteinmix ke label par jo likha hai woh dikhaya hai. "
                "[[CONFIRM: age and serving guidance]]  #ad #paidpartnership [[CONFIRM: brand handle to tag]]",
        tone=dict(
            summary="Fast, reassuring and clinical: a doctor teaching label literacy, with Hindi explanation and English terms.",
            delivery=["Pace: quick and energetic, as in her posts, but slow down for quoted label lines.",
                      "Language: Hindi explanation with English product and label terms (English-only would feel foreign).",
                      "Direct 'aap' address, split-screen layout, 'Save this reel' close.",
                      "Teach how to read a label; never recommend the product or a dose."],
            language="Hindi + English terms", camera="Clinic set, split-screen"),
        creator_avoid=["English-only audio or a scripted sales pitch without medical context (flagged as foreign to her style).",
                       "Stating or implying that any child needs protein supplementation, or recommending a dose; her authority makes this high-stakes.",
                       "Product-review language that ranks Little Joys against other brands; her review posts name other brands."],
    ),
}

SECTIONS = ["concept", "hooks", "script", "visuals", "onscreen", "cta"]

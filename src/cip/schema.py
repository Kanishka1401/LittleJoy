"""Column roles for every dataset.

Single source of truth used by loaders, validators and (later) analysis code.
Roles:
  ids          – keys / URLs, never modelled
  dates        – parsed to datetime
  numeric      – measured or counted values
  categorical  – single-valued labels
  multilabel   – ';'-separated multi-valued labels (explode before analysis)
  text         – free text (transcripts, captions, copy)
  json         – JSON-encoded string
  ai_labelled  – columns produced by a model/LLM, NOT platform-reported or human-verified
"""

ADS = {
    "ids": ["ad_id", "meta_ad_library_id", "video_url"],
    "dates": ["launch_date", "stopped_date"],
    "numeric": [
        "days_live", "duration_s", "spend_inr", "impressions", "video_3s_views",
        "thruplays", "link_clicks", "add_to_carts", "purchases", "revenue_inr",
    ],
    "categorical": [
        "language", "hook_type", "hook_driver", "hook_delivered_by", "ad_format",
        "story_structure", "main_benefit", "performance_style", "humour",
        "creator_type", "creator_gender", "creator_age", "people_on_screen",
        "child_on_screen", "child_age", "child_in_first_3s", "brand_first_said",
        "brand_said_aloud", "product_form", "product_shown_as", "production",
        "audio", "music", "captions", "language_mixing", "first_frame", "setting",
        "cta_type", "offer",
    ],
    "multilabel": [
        "child_role", "demo_shown", "proof_used", "persuasion", "narratives",
        "ad_categories", "claims_made",
    ],
    "text": ["ad_copy", "transcript", "hook_line", "on_screen_text", "hook_text_on_screen"],
    # Everything that is neither an id, a date, nor a platform metric.
    "ai_labelled": [
        "language", "hook_line", "hook_type", "hook_driver", "hook_delivered_by",
        "hook_text_on_screen", "ad_format", "story_structure", "main_benefit",
        "performance_style", "humour", "creator_type", "creator_gender", "creator_age",
        "people_on_screen", "child_on_screen", "child_age", "child_role",
        "child_in_first_3s", "brand_first_said", "brand_said_aloud", "product_form",
        "product_shown_as", "demo_shown", "proof_used", "persuasion", "production",
        "audio", "music", "captions", "language_mixing", "first_frame", "setting",
        "cta_type", "offer", "narratives", "ad_categories", "claims_made",
        "transcript", "on_screen_text", "duration_s",
    ],
    "outcome": ["spend_inr", "impressions", "video_3s_views", "thruplays",
                "link_clicks", "add_to_carts", "purchases", "revenue_inr"],
}

CREATORS = {
    "ids": ["creator_id", "handle", "profile_url"],
    "numeric": ["followers", "following", "total_posts", "posts_in_file"],
    "categorical": ["verified"],
    "text": ["name", "bio", "persona", "persona_description", "feed_story", "voice",
             "language_use", "catchphrases", "themes", "format_habits",
             "what_feels_native", "what_would_feel_foreign"],
    "json": ["audience_read"],
    "ai_labelled": ["persona", "persona_description", "feed_story", "voice",
                    "language_use", "catchphrases", "themes", "format_habits",
                    "what_feels_native", "what_would_feel_foreign", "audience_read"],
}

POSTS = {
    "ids": ["creator_id", "handle", "post_url"],
    "dates": ["posted_on"],
    "numeric": ["duration_s", "plays", "likes", "comments", "reshares",
                "production_quality_1to5"],
    "categorical": ["type", "content_type", "content_form", "creator_on_camera",
                    "children_on_camera", "presenter_age", "presenter_gender",
                    "language", "product_shown", "is_sponsored", "transcript_language"],
    "multilabel": ["child_ages", "brands_visible"],
    "text": ["caption", "topic", "hook_style", "setting", "tone", "audience_signal",
             "on_screen_text", "what_stands_out", "transcript"],
    "ai_labelled": ["content_type", "content_form", "topic", "hook_style",
                    "creator_on_camera", "children_on_camera", "child_ages",
                    "presenter_age", "presenter_gender", "language", "setting", "tone",
                    "product_shown", "is_sponsored", "brands_visible",
                    "production_quality_1to5", "audience_signal", "on_screen_text",
                    "what_stands_out", "transcript", "transcript_language"],
    "outcome": ["plays", "likes", "comments", "reshares"],
}

AUDIENCE = {
    "ids": ["creator_id", "handle"],
    "dates": ["as_of"],
    "numeric": ["women_pct", "men_pct"],
    "categorical": ["platform"],
    "multilabel": ["age_split", "top_cities", "top_countries", "brands_in_past_year"],
    "ai_labelled": [],  # platform-reported demographics (provenance still to confirm)
}

SCHEMAS = {"ads": ADS, "creators": CREATORS, "posts": POSTS, "audience": AUDIENCE}

EXPECTED_ROWS = {"ads": 100, "creators": 20, "posts": 392, "audience": 3}
EXPECTED_COLS = {"ads": 56, "creators": 21, "posts": 32, "audience": 10}

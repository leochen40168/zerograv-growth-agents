# ZeroGrav Growth Agents MVP

ZeroGrav Growth Agents MVP is a local Streamlit dashboard for planning daily cold-start content, generating prompt files, tracking drafts for human review, exporting website and social content for manual copy publishing, managing seller leads, and recording manual metrics.

This project does not automatically operate Facebook, scrape groups, send messages, comment, like, publish website posts, publish WordPress posts, or hard-code API keys. Generated content still requires human review and manual publishing.

## Installation

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
copy .env.example .env
```

Edit `.env` with only the credentials you plan to use. Keep `.env` local and do not commit it.

## Run Streamlit

```powershell
streamlit run src/app.py
```

## Environment

OpenAI draft generation is optional:

```powershell
OPENAI_API_KEY=your_api_key_here
OPENAI_MODEL=gpt-4.1-mini
```

WordPress draft creation is an optional future feature:

```powershell
WORDPRESS_URL=https://your-wordpress-site.com
WORDPRESS_USERNAME=your_username
WORDPRESS_APP_PASSWORD=your_application_password
```

The OpenAI key is only used when a human clicks draft generation or runs the draft CLI. WordPress credentials are reserved for optional future draft-only workflows. They are not used for Facebook, website publishing, posting, comments, messages, or likes.

## Daily SOP

1. Open `Daily Growth Workflow` and click `Create Daily Tasks`.
2. Open `Generate Content Prompts` and create prompt markdown for selected topics.
3. Open `Content Draft Generator` and generate local draft markdown.
4. Open `Content Review Queue` and click `Scan Drafts`.
5. Review every draft manually.
6. Open `Website / Social Content Exporter` and click `Export Drafts for Manual Publishing`.
7. Manually copy approved website content to the zerograv.com.tw website admin.
8. Manually publish approved content to the Facebook page or Facebook group.
9. If there is an inquiry, add it in `Seller Lead Tracker`.
10. In the evening, enter manual performance numbers in `Metrics Tracker`.

The SOP is intentionally human-in-the-loop. The dashboard creates local records, draft files, and manual copy export files only.

## Generate Prompts

In Streamlit, open `Generate Content Prompts`, select a topic from `data/topics.csv`, and click `Generate Prompts`.

CLI:

```powershell
python src/article_generator.py --topic-id 1
```

Generated prompt markdown files are saved under `outputs/generated_prompts/`. This only fills prompt templates. It does not call OpenAI, WordPress, Facebook, or publish anything automatically.

## Generate Content Drafts

Generate one draft from a specific prompt:

```powershell
python src/content_draft_generator.py --prompt-path outputs/generated_prompts/topic-1-seo-article.md
```

Generate all drafts for a topic:

```powershell
python src/content_draft_generator.py --topic-id 1
```

Draft files are saved to `outputs/drafts/` with `review_status: draft` metadata. The generated files are drafts for human review and are not automatically published, posted, commented, messaged, liked, or sent anywhere.

## Content Review Queue

The `Content Review Queue` tracks markdown drafts in `outputs/drafts/` so the team can review, approve, rewrite, archive, or mark content as manually published. Review items are stored in `data/content_reviews.csv`.

Suggested review flow:

1. Generate Drafts
2. Scan Drafts
3. Review items in `needs_review`
4. Mark each item `approved` or `needs_rewrite`
5. After approval, export drafts for manual publishing
6. After manual publishing, mark the item `published`

## Website / Social Content Exporter

This feature creates manual copy files in `outputs/exports/` from markdown drafts in `outputs/drafts/`. It does not publish to zerograv.com.tw, Facebook pages, Facebook groups, WordPress, or any other channel.

Export one draft:

```powershell
python -c "from src.website_content_exporter import export_draft; print(export_draft('outputs/drafts/draft-topic-1-seo-article.md'))"
```

Export drafts for a topic:

```powershell
python -c "from src.website_content_exporter import export_drafts_for_topic; print(export_drafts_for_topic(1))"
```

Exported files are saved as `outputs/exports/export-{original-draft-filename}` and include metadata with `publish_method: manual_copy`.

## Optional Future WordPress Draft Publisher

WordPress draft publishing is not part of the current main workflow because ZeroGrav currently uses zerograv.com.tw plus Facebook page and group channels. If WordPress is added later, draft-only integration can remain optional and must still require human review before publishing.

## Posting Task Manager

The dashboard includes a `Posting Task Manager` section for manually planning Facebook page, Facebook group, website, and LINE posting tasks. Tasks are saved to `data/posting_tasks.csv`. This is only a planning table; it does not publish anything automatically.

Allowed task statuses:

- `pending`
- `generated`
- `reviewed`
- `published`
- `skipped`

## Seller Lead Tracker

The dashboard includes a `Seller Lead Tracker` section for manually tracking used-equipment seller leads from Facebook pages, Facebook groups, LINE, website forms, phone calls, and other sources. Leads are saved to `data/seller_leads.csv`. This is only a manual tracking table; it does not send messages or contact sellers automatically.

Recommended seller data fields:

- Seller name
- Lead source
- Equipment type
- Brand
- Model
- Equipment location
- Contact method
- Contact value
- Asking price
- Equipment condition
- Whether it powers on
- Calibration report availability
- Software license status
- Photos
- Next action
- Internal notes

## Metrics Tracker

The `Metrics Tracker` records manual performance data for cold-start content and posting tasks. It helps compare topics, platforms, and content types by engagement and seller lead output.

This is a local CSV tracker only. It does not fetch Facebook data, call APIs, publish posts, send messages, or automate engagement.

Suggested daily metrics:

- Impressions or reach
- Reactions
- Comments
- Shares
- Clicks
- Messages
- Seller leads
- Listed items
- Notes about what worked or did not work

Use metrics to identify topics, platforms, and content types that deserve more manual effort.

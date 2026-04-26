from datetime import date
from pathlib import Path

import pandas as pd
import streamlit as st
from dotenv import load_dotenv

from article_generator import ArticleGeneratorError, generate_prompts_for_topic
from content_draft_generator import ContentDraftGeneratorError, generate_drafts_for_topic
from daily_workflow import DailyWorkflowError, create_daily_tasks, get_pending_topics, mark_topics_as_in_progress
from lead_tracker import ALLOWED_LEAD_STATUSES, LeadTrackerError, add_lead, get_new_leads, load_leads, update_lead_status
from metrics_tracker import MetricsTrackerError, add_metric, load_metrics, summarize_metrics, update_metric
from review_queue import ALLOWED_REVIEW_STATUSES, ReviewQueueError, get_reviews_by_status, load_reviews, scan_drafts, update_review_status
from task_manager import ALLOWED_STATUSES, TaskManagerError, add_task, get_today_tasks, load_tasks, update_task_status
from wordpress_draft_publisher import WordPressDraftPublisherError, publish_drafts_for_topic


BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
GENERATED_PROMPTS_DIR = BASE_DIR / "outputs" / "generated_prompts"
DRAFTS_DIR = BASE_DIR / "outputs" / "drafts"
CSV_FILES = {
    "Topics": ("topics.csv", DATA_DIR / "topics.csv"),
    "Posting Tasks": ("posting_tasks.csv", DATA_DIR / "posting_tasks.csv"),
    "Seller Leads": ("seller_leads.csv", DATA_DIR / "seller_leads.csv"),
    "Content Reviews": ("content_reviews.csv", DATA_DIR / "content_reviews.csv"),
    "Metrics": ("metrics.csv", DATA_DIR / "metrics.csv"),
}


def ensure_csv(path: Path) -> pd.DataFrame:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not path.exists():
        path.write_text("", encoding="utf-8")
    try:
        return pd.read_csv(path)
    except pd.errors.EmptyDataError:
        return pd.DataFrame()


def get_topic_ids(topics_df: pd.DataFrame) -> list[int]:
    if topics_df.empty or "id" not in topics_df.columns:
        return []
    return [int(topic_id) for topic_id in pd.to_numeric(topics_df["id"], errors="coerce").dropna()]


def show_prompt_generator(topics_df: pd.DataFrame) -> None:
    st.header("Generate Content Prompts")
    required = {"id", "topic", "category", "target_audience", "intent", "cta"}
    if topics_df.empty:
        st.info("topics.csv has no topics yet.")
        return
    if not required.issubset(topics_df.columns):
        st.error("topics.csv is missing required columns: " + ", ".join(sorted(required - set(topics_df.columns))))
        return
    topic_options = {f"{row.id} - {row.topic}": int(row.id) for row in topics_df.itertuples(index=False)}
    selected_topic = st.selectbox("Select topic", list(topic_options.keys()))
    if st.button("Generate Prompts"):
        try:
            paths = generate_prompts_for_topic(topic_options[selected_topic])
        except ArticleGeneratorError as error:
            st.error(str(error))
        else:
            st.success("Prompts generated.")
            for path in paths:
                st.code(path)


def show_daily_growth_workflow(topics_df: pd.DataFrame) -> None:
    st.header("Daily Growth Workflow")
    st.info("This only creates local posting tasks for humans. It does not post, publish, message, comment, like, call OpenAI, or call WordPress.")
    pending_count = int((topics_df["status"] == "pending").sum()) if not topics_df.empty and "status" in topics_df.columns else 0
    st.metric("Pending topics", pending_count)
    topic_limit = st.number_input("topic_limit", min_value=1, value=3, step=1)
    workflow_date = st.date_input("workflow date", value=date.today())
    try:
        preview = get_pending_topics(int(topic_limit))
    except DailyWorkflowError as error:
        st.error(str(error))
        preview = pd.DataFrame()
    st.subheader("Pending topics preview")
    st.dataframe(preview, use_container_width=True)
    if st.button("Create Daily Tasks"):
        try:
            task_ids = create_daily_tasks(date=workflow_date.isoformat(), topic_limit=int(topic_limit))
        except (DailyWorkflowError, TaskManagerError) as error:
            st.error(str(error))
        else:
            st.success("Daily tasks created." if task_ids else "No new tasks were created.")
            st.write(task_ids)
    if not preview.empty:
        options = {f"{row.id} - {row.topic}": int(row.id) for row in preview.itertuples(index=False)}
        selected = st.multiselect("Topics to mark as in_progress", list(options.keys()))
        if st.button("Mark Selected Topics as In Progress"):
            try:
                mark_topics_as_in_progress([options[label] for label in selected])
            except DailyWorkflowError as error:
                st.error(str(error))
            else:
                st.success("Selected topics marked as in_progress.")
                st.rerun()


def show_content_draft_generator(topics_df: pd.DataFrame) -> None:
    st.header("Content Draft Generator")
    topic_ids = get_topic_ids(topics_df)
    topic_id = st.selectbox("Draft topic id", topic_ids) if topic_ids else st.number_input("Draft topic id", min_value=1, step=1)
    prompts = sorted(GENERATED_PROMPTS_DIR.glob(f"topic-{int(topic_id)}-*.md"))
    st.info("No generated prompts found. Run Generate Content Prompts first." if not prompts else f"Found {len(prompts)} generated prompt files.")
    if st.button("Generate Drafts from Existing Prompts"):
        try:
            paths = generate_drafts_for_topic(int(topic_id))
        except ContentDraftGeneratorError as error:
            st.error(str(error))
        else:
            st.success("Drafts generated for human review.")
            for path in paths:
                st.code(path)


def show_content_review_queue() -> None:
    st.header("Content Review Queue")
    st.info("This only tracks local draft review status. It does not publish or call external APIs.")
    if st.button("Scan Drafts"):
        try:
            created = scan_drafts()
        except ReviewQueueError as error:
            st.error(str(error))
        else:
            st.success("Review items created." if created else "No new draft files found.")
            st.write(created)
    try:
        reviews = load_reviews()
        needs_review = get_reviews_by_status("needs_review")
    except ReviewQueueError as error:
        st.error(str(error))
        return
    st.subheader("All review items")
    st.dataframe(reviews, use_container_width=True)
    st.subheader("Needs review")
    st.dataframe(needs_review, use_container_width=True)
    if reviews.empty:
        st.info("No review items to update.")
        return
    ids = [int(item) for item in pd.to_numeric(reviews["id"], errors="coerce").dropna()]
    with st.form("update_review_status"):
        review_id = st.selectbox("review id", ids)
        status = st.selectbox("review status", sorted(ALLOWED_REVIEW_STATUSES), index=0)
        reviewer = st.text_input("reviewer")
        notes = st.text_area("review_notes")
        submitted = st.form_submit_button("Update")
    if submitted:
        try:
            update_review_status(review_id, status, reviewer=reviewer, review_notes=notes)
        except ReviewQueueError as error:
            st.error(str(error))
        else:
            st.success(f"Review item updated: {review_id}")
            st.rerun()


def show_wordpress_draft_publisher(topics_df: pd.DataFrame) -> None:
    st.header("WordPress Draft Publisher")
    st.info("This creates WordPress posts with status=draft only. It does not publish.")
    topic_ids = get_topic_ids(topics_df)
    topic_id = st.selectbox("WordPress topic id", topic_ids) if topic_ids else st.number_input("WordPress topic id", min_value=1, step=1)
    drafts = sorted(DRAFTS_DIR.glob(f"draft-topic-{int(topic_id)}-*seo-article*.md"))
    st.info("No SEO article draft found in outputs/drafts for this topic." if not drafts else f"Found {len(drafts)} SEO article draft file(s).")
    if st.button("Publish SEO Draft to WordPress Draft"):
        try:
            responses = publish_drafts_for_topic(int(topic_id))
        except WordPressDraftPublisherError as error:
            st.error(str(error))
        else:
            st.success("WordPress draft created. Review it manually before publishing.")
            for response in responses:
                st.json(response)


def show_posting_task_manager() -> None:
    st.header("Posting Task Manager")
    try:
        today_tasks = get_today_tasks()
        tasks = load_tasks()
    except TaskManagerError as error:
        st.error(str(error))
        return
    st.subheader("Today Tasks")
    st.dataframe(today_tasks, use_container_width=True)
    st.subheader("All Posting Tasks")
    st.dataframe(tasks, use_container_width=True)
    with st.form("add_posting_task"):
        task_date = st.date_input("date", value=date.today())
        platform = st.text_input("platform", value="Facebook Page")
        destination = st.text_input("destination", value="ZeroGrav")
        post_type = st.text_input("post_type", value="Page Post")
        topic_id = st.number_input("topic_id", min_value=1, step=1)
        status = st.selectbox("status", sorted(ALLOWED_STATUSES), index=0)
        result_notes = st.text_area("result_notes")
        submitted = st.form_submit_button("Add Task")
    if submitted:
        try:
            task_id = add_task(task_date.isoformat(), platform, destination, post_type, int(topic_id), status, result_notes)
        except TaskManagerError as error:
            st.error(str(error))
        else:
            st.success(f"Task added: {task_id}")
            st.rerun()
    if tasks.empty:
        st.info("No tasks to update.")
        return
    ids = [int(item) for item in pd.to_numeric(tasks["id"], errors="coerce").dropna()]
    with st.form("update_posting_task_status"):
        task_id = st.selectbox("task id", ids)
        status = st.selectbox("new status", sorted(ALLOWED_STATUSES), index=0)
        result_notes = st.text_area("result_notes", key="update_result_notes")
        submitted = st.form_submit_button("Update")
    if submitted:
        try:
            update_task_status(task_id, status, result_notes)
        except TaskManagerError as error:
            st.error(str(error))
        else:
            st.success(f"Task updated: {task_id}")
            st.rerun()


def show_seller_lead_tracker() -> None:
    st.header("Seller Lead Tracker")
    try:
        leads = load_leads()
        new_leads = get_new_leads()
    except LeadTrackerError as error:
        st.error(str(error))
        return
    st.subheader("All Seller Leads")
    st.dataframe(leads, use_container_width=True)
    st.subheader("New Leads")
    st.dataframe(new_leads, use_container_width=True)
    with st.form("add_seller_lead"):
        lead_date = st.date_input("lead date", value=date.today())
        name = st.text_input("name")
        source = st.text_input("source", value="Facebook Page")
        equipment_type = st.text_input("equipment_type", value="Vision Measuring Machine")
        brand = st.text_input("brand")
        model = st.text_input("model")
        location = st.text_input("location")
        contact_method = st.text_input("contact_method", value="LINE")
        contact_value = st.text_input("contact_value")
        asking_price = st.text_input("asking_price")
        condition = st.text_area("condition")
        status = st.selectbox("lead status", sorted(ALLOWED_LEAD_STATUSES), index=0)
        next_action = st.text_input("next_action")
        notes = st.text_area("notes")
        submitted = st.form_submit_button("Add Lead")
    if submitted:
        try:
            lead_id = add_lead(lead_date.isoformat(), name, source, equipment_type, brand, model, location, contact_method, contact_value, asking_price, condition, status, next_action, notes)
        except LeadTrackerError as error:
            st.error(str(error))
        else:
            st.success(f"Lead added: {lead_id}")
            st.rerun()
    if leads.empty:
        st.info("No seller leads to update.")
        return
    ids = [int(item) for item in pd.to_numeric(leads["id"], errors="coerce").dropna()]
    with st.form("update_seller_lead_status"):
        lead_id = st.selectbox("lead id", ids)
        status = st.selectbox("new lead status", sorted(ALLOWED_LEAD_STATUSES), index=0)
        next_action = st.text_input("next_action", key="lead_next_action")
        notes = st.text_area("notes", key="lead_update_notes")
        submitted = st.form_submit_button("Update Lead")
    if submitted:
        try:
            update_lead_status(lead_id, status, next_action=next_action, notes=notes)
        except LeadTrackerError as error:
            st.error(str(error))
        else:
            st.success(f"Lead updated: {lead_id}")
            st.rerun()


def show_metrics_tracker() -> None:
    st.header("Metrics Tracker")
    st.info("Manual metrics only. This does not fetch Facebook data or call external APIs.")
    try:
        metrics = load_metrics()
        summary = summarize_metrics()
    except MetricsTrackerError as error:
        st.error(str(error))
        return
    cols = st.columns(5)
    cols[0].metric("Total impressions", summary["total_impressions"])
    cols[1].metric("Total comments", summary["total_comments"])
    cols[2].metric("Total messages", summary["total_messages"])
    cols[3].metric("Total leads", summary["total_leads"])
    cols[4].metric("Listed items", summary["total_listed_items"])
    st.write("Top platform by leads:", summary["top_platform_by_leads"] or "N/A")
    st.write("Top topic by leads:", summary["top_topic_by_leads"] or "N/A")
    st.dataframe(metrics, use_container_width=True)
    with st.form("add_metric"):
        metric_date = st.date_input("metric date", value=date.today())
        task_id = st.text_input("task_id")
        topic_id = st.text_input("topic_id")
        platform = st.text_input("metric platform", value="Facebook Page")
        content_type = st.text_input("content_type", value="Page Post")
        impressions = st.number_input("impressions", min_value=0, step=1)
        reactions = st.number_input("reactions", min_value=0, step=1)
        comments = st.number_input("comments", min_value=0, step=1)
        shares = st.number_input("shares", min_value=0, step=1)
        clicks = st.number_input("clicks", min_value=0, step=1)
        messages = st.number_input("messages", min_value=0, step=1)
        leads = st.number_input("leads", min_value=0, step=1)
        listed_items = st.number_input("listed_items", min_value=0, step=1)
        notes = st.text_area("metric notes")
        submitted = st.form_submit_button("Add Metric")
    if submitted:
        try:
            metric_id = add_metric(metric_date.isoformat(), task_id, topic_id, platform, content_type, impressions, reactions, comments, shares, clicks, messages, leads, listed_items, notes)
        except MetricsTrackerError as error:
            st.error(str(error))
        else:
            st.success(f"Metric added: {metric_id}")
            st.rerun()
    if metrics.empty:
        st.info("No metrics to update.")
        return
    ids = [int(item) for item in pd.to_numeric(metrics["id"], errors="coerce").dropna()]
    with st.form("update_metric"):
        metric_id = st.selectbox("metric id", ids)
        impressions = st.number_input("update impressions", min_value=0, step=1)
        comments = st.number_input("update comments", min_value=0, step=1)
        messages = st.number_input("update messages", min_value=0, step=1)
        leads = st.number_input("update leads", min_value=0, step=1)
        listed_items = st.number_input("update listed_items", min_value=0, step=1)
        notes = st.text_area("update notes")
        submitted = st.form_submit_button("Update Metric")
    if submitted:
        try:
            update_metric(metric_id, impressions=int(impressions), comments=int(comments), messages=int(messages), leads=int(leads), listed_items=int(listed_items), notes=notes)
        except MetricsTrackerError as error:
            st.error(str(error))
        else:
            st.success(f"Metric updated: {metric_id}")
            st.rerun()


load_dotenv(BASE_DIR / ".env")
st.set_page_config(page_title="ZeroGrav Growth Agents MVP", layout="wide")
st.title("ZeroGrav Growth Agents MVP")
st.caption("Manual daily growth dashboard. No automatic Facebook actions, WordPress publishing, OpenAI calls, or external API calls run unless a human explicitly uses the related draft-only tools.")

dataframes = {label: (filename, ensure_csv(path)) for label, (filename, path) in CSV_FILES.items()}
cols = st.columns(len(dataframes))
for col, (label, (_, df)) in zip(cols, dataframes.items()):
    col.metric(label, len(df))

with st.expander("CSV Data Preview", expanded=False):
    for _, (filename, df) in dataframes.items():
        st.subheader(filename)
        st.dataframe(df, use_container_width=True)

topics_df = dataframes["Topics"][1]
with st.expander("Daily Growth Workflow", expanded=True):
    show_daily_growth_workflow(topics_df)
with st.expander("Generate Content Prompts", expanded=False):
    show_prompt_generator(topics_df)
with st.expander("Content Draft Generator", expanded=False):
    show_content_draft_generator(topics_df)
with st.expander("Content Review Queue", expanded=False):
    show_content_review_queue()
with st.expander("WordPress Draft Publisher", expanded=False):
    show_wordpress_draft_publisher(topics_df)
with st.expander("Posting Task Manager", expanded=False):
    show_posting_task_manager()
with st.expander("Seller Lead Tracker", expanded=False):
    show_seller_lead_tracker()
with st.expander("Metrics Tracker", expanded=False):
    show_metrics_tracker()

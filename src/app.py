from datetime import date
from pathlib import Path

import pandas as pd
import streamlit as st
from dotenv import load_dotenv

from article_generator import ArticleGeneratorError, generate_prompts_for_topic
from content_draft_generator import ContentDraftGeneratorError, generate_drafts_for_topic
from daily_workflow import DailyWorkflowError, create_daily_tasks, get_pending_topics, mark_topics_as_in_progress
from email_sender import EmailSenderError, load_email_log, send_vendor_email
from lead_tracker import ALLOWED_LEAD_STATUSES, LeadTrackerError, add_lead, get_new_leads, load_leads, update_lead_status
from metrics_tracker import MetricsTrackerError, add_metric, load_metrics, summarize_metrics, update_metric
from review_queue import ALLOWED_REVIEW_STATUSES, ReviewQueueError, get_reviews_by_status, load_reviews, scan_drafts, update_review_status
from task_manager import ALLOWED_STATUSES, TaskManagerError, add_task, get_today_tasks, load_tasks, update_task_status
from vendor_outreach import ALLOWED_CONTACT_STATUSES, ALLOWED_SOURCE_TYPES, VendorOutreachError, add_vendor, generate_vendor_email, get_vendors_by_status, load_vendors, update_vendor_status
from website_content_exporter import WebsiteContentExporterError, export_drafts_for_topic


BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
GENERATED_PROMPTS_DIR = BASE_DIR / "outputs" / "generated_prompts"
DRAFTS_DIR = BASE_DIR / "outputs" / "drafts"
CSV_FILES = {
    "內容主題": ("topics.csv", DATA_DIR / "topics.csv"),
    "發文任務": ("posting_tasks.csv", DATA_DIR / "posting_tasks.csv"),
    "賣家線索": ("seller_leads.csv", DATA_DIR / "seller_leads.csv"),
    "合作廠商": ("vendors.csv", DATA_DIR / "vendors.csv"),
    "開發信紀錄": ("email_outreach_log.csv", DATA_DIR / "email_outreach_log.csv"),
    "審稿清單": ("content_reviews.csv", DATA_DIR / "content_reviews.csv"),
    "成效紀錄": ("metrics.csv", DATA_DIR / "metrics.csv"),
}


def show_error(error: Exception) -> None:
    st.error(f"發生錯誤：{error}")


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
    st.header("產生內容 Prompt")
    required = {"id", "topic", "category", "target_audience", "intent", "cta"}
    if topics_df.empty:
        st.info("topics.csv 目前沒有主題資料。")
        return
    if not required.issubset(topics_df.columns):
        st.error("topics.csv 缺少必要欄位：" + ", ".join(sorted(required - set(topics_df.columns))))
        return
    topic_options = {f"{row.id} - {row.topic}": int(row.id) for row in topics_df.itertuples(index=False)}
    selected_topic = st.selectbox("選擇內容主題", list(topic_options.keys()))
    if st.button("產生 Prompt"):
        try:
            paths = generate_prompts_for_topic(topic_options[selected_topic])
        except ArticleGeneratorError as error:
            show_error(error)
        else:
            st.success("Prompt 已產生。")
            for path in paths:
                st.code(path)


def show_daily_growth_workflow(topics_df: pd.DataFrame) -> None:
    st.header("每日冷啟動流程")
    st.info("這裡只會建立本機發文任務，供人工執行。不會自動發文、發布、私訊、留言、按讚，也不會自動呼叫 OpenAI 或 WordPress。")
    pending_count = int((topics_df["status"] == "pending").sum()) if not topics_df.empty and "status" in topics_df.columns else 0
    st.metric("待處理主題", pending_count)
    topic_limit = st.number_input("每日主題數量", min_value=1, value=3, step=1)
    workflow_date = st.date_input("流程日期", value=date.today())
    try:
        preview = get_pending_topics(int(topic_limit))
    except DailyWorkflowError as error:
        show_error(error)
        preview = pd.DataFrame()
    st.subheader("待處理主題預覽")
    st.dataframe(preview, use_container_width=True)
    if st.button("建立每日任務"):
        try:
            task_ids = create_daily_tasks(date=workflow_date.isoformat(), topic_limit=int(topic_limit))
        except (DailyWorkflowError, TaskManagerError) as error:
            show_error(error)
        else:
            st.success("每日任務已建立。" if task_ids else "沒有新的任務需要建立。")
            st.write(task_ids)
    if not preview.empty:
        options = {f"{row.id} - {row.topic}": int(row.id) for row in preview.itertuples(index=False)}
        selected = st.multiselect("要標記為進行中的主題", list(options.keys()))
        if st.button("將選取主題標記為進行中"):
            try:
                mark_topics_as_in_progress([options[label] for label in selected])
            except DailyWorkflowError as error:
                show_error(error)
            else:
                st.success("選取主題已標記為進行中。")
                st.rerun()


def show_content_draft_generator(topics_df: pd.DataFrame) -> None:
    st.header("產生內容草稿")
    topic_ids = get_topic_ids(topics_df)
    topic_id = st.selectbox("草稿主題 ID", topic_ids) if topic_ids else st.number_input("草稿主題 ID", min_value=1, step=1)
    prompts = sorted(GENERATED_PROMPTS_DIR.glob(f"topic-{int(topic_id)}-*.md"))
    st.info("找不到已產生的 Prompt，請先執行「產生內容 Prompt」。" if not prompts else f"找到 {len(prompts)} 個 Prompt 檔案。")
    if st.button("用既有 Prompt 產生草稿"):
        try:
            paths = generate_drafts_for_topic(int(topic_id))
        except ContentDraftGeneratorError as error:
            show_error(error)
        else:
            st.success("草稿已產生，請人工審稿。")
            for path in paths:
                st.code(path)


def show_content_review_queue() -> None:
    st.header("內容審稿清單")
    st.info("這裡只會追蹤本機草稿審核狀態。不會發布內容，也不會呼叫外部 API。")
    if st.button("掃描草稿"):
        try:
            created = scan_drafts()
        except ReviewQueueError as error:
            show_error(error)
        else:
            st.success("審稿項目已建立。" if created else "沒有找到新的草稿檔案。")
            st.write(created)
    try:
        reviews = load_reviews()
        needs_review = get_reviews_by_status("needs_review")
    except ReviewQueueError as error:
        show_error(error)
        return
    st.subheader("全部審稿項目")
    st.dataframe(reviews, use_container_width=True)
    st.subheader("待審稿")
    st.dataframe(needs_review, use_container_width=True)
    if reviews.empty:
        st.info("目前沒有可更新的審稿項目。")
        return
    ids = [int(item) for item in pd.to_numeric(reviews["id"], errors="coerce").dropna()]
    with st.form("update_review_status"):
        review_id = st.selectbox("審稿項目 ID", ids)
        status = st.selectbox("審稿狀態", sorted(ALLOWED_REVIEW_STATUSES), index=0)
        reviewer = st.text_input("審稿人")
        notes = st.text_area("審稿備註")
        submitted = st.form_submit_button("更新")
    if submitted:
        try:
            update_review_status(review_id, status, reviewer=reviewer, review_notes=notes)
        except ReviewQueueError as error:
            show_error(error)
        else:
            st.success(f"審稿項目已更新：{review_id}")
            st.rerun()


def show_website_social_content_exporter(topics_df: pd.DataFrame) -> None:
    st.header("網站 / 社群內容匯出")
    st.info("不會自動發布到網站\n\n不會自動發布到 Facebook\n\n只會產生人工複製發布用的內容檔案")
    topic_ids = get_topic_ids(topics_df)
    topic_id = st.selectbox("匯出主題 ID", topic_ids) if topic_ids else st.number_input("匯出主題 ID", min_value=1, step=1)
    drafts = sorted(DRAFTS_DIR.glob(f"draft-topic-{int(topic_id)}-*.md"))
    st.info("這個主題在 outputs/drafts 找不到草稿檔案。" if not drafts else f"找到 {len(drafts)} 個草稿檔案。")
    if st.button("匯出人工發布用草稿"):
        try:
            paths = export_drafts_for_topic(int(topic_id))
        except WebsiteContentExporterError as error:
            show_error(error)
        else:
            st.success("已匯出人工複製發布用內容。")
            for path in paths:
                st.code(path)


def show_posting_task_manager() -> None:
    st.header("發文任務管理")
    try:
        today_tasks = get_today_tasks()
        tasks = load_tasks()
    except TaskManagerError as error:
        show_error(error)
        return
    st.subheader("今日任務")
    st.dataframe(today_tasks, use_container_width=True)
    st.subheader("全部發文任務")
    st.dataframe(tasks, use_container_width=True)
    with st.form("add_posting_task"):
        task_date = st.date_input("任務日期", value=date.today())
        platform = st.text_input("平台", value="Facebook Page")
        destination = st.text_input("發布位置", value="ZeroGrav")
        post_type = st.text_input("內容類型", value="Page Post")
        topic_id = st.number_input("主題 ID", min_value=1, step=1)
        status = st.selectbox("任務狀態", sorted(ALLOWED_STATUSES), index=0)
        result_notes = st.text_area("結果備註")
        submitted = st.form_submit_button("新增任務")
    if submitted:
        try:
            task_id = add_task(task_date.isoformat(), platform, destination, post_type, int(topic_id), status, result_notes)
        except TaskManagerError as error:
            show_error(error)
        else:
            st.success(f"任務已新增：{task_id}")
            st.rerun()
    if tasks.empty:
        st.info("目前沒有可更新的任務。")
        return
    ids = [int(item) for item in pd.to_numeric(tasks["id"], errors="coerce").dropna()]
    with st.form("update_posting_task_status"):
        task_id = st.selectbox("任務 ID", ids)
        status = st.selectbox("新狀態", sorted(ALLOWED_STATUSES), index=0)
        result_notes = st.text_area("結果備註", key="update_result_notes")
        submitted = st.form_submit_button("更新")
    if submitted:
        try:
            update_task_status(task_id, status, result_notes)
        except TaskManagerError as error:
            show_error(error)
        else:
            st.success(f"任務已更新：{task_id}")
            st.rerun()


def show_vendor_email_outreach_agent() -> None:
    st.header("廠商開發信助手")
    st.info("只有在 EMAIL_SEND_ENABLED=true 時才會真的寄信。請勿寄給沒有公開來源網址 source_url 的廠商，也不要寄給已標記 opted_out 或 not_interested 的廠商。")
    try:
        vendors = load_vendors()
        email_log = load_email_log()
    except (VendorOutreachError, EmailSenderError) as error:
        show_error(error)
        return

    st.subheader("合作廠商")
    st.dataframe(vendors, use_container_width=True)

    with st.form("add_vendor"):
        company_name = st.text_input("公司名稱")
        website = st.text_input("官網")
        email = st.text_input("Email")
        phone = st.text_input("電話")
        category = st.text_input("設備類別", value="二手儀器 / 量測儀器 / 檢測設備")
        source_url = st.text_input("Email 來源網址")
        source_type = st.selectbox("來源類型", sorted(ALLOWED_SOURCE_TYPES), index=sorted(ALLOWED_SOURCE_TYPES).index("manual"))
        contact_status = st.selectbox("聯繫狀態", sorted(ALLOWED_CONTACT_STATUSES), index=sorted(ALLOWED_CONTACT_STATUSES).index("new"))
        last_contacted = st.text_input("上次聯繫日期")
        next_action = st.text_input("下一步動作")
        notes = st.text_area("備註")
        submitted = st.form_submit_button("新增廠商")
    if submitted:
        try:
            vendor_id = add_vendor(company_name, website=website, email=email, phone=phone, category=category, source_url=source_url, source_type=source_type, contact_status=contact_status, last_contacted=last_contacted, next_action=next_action, notes=notes)
        except VendorOutreachError as error:
            show_error(error)
        else:
            st.success(f"廠商已新增：{vendor_id}")
            st.rerun()

    st.subheader("依狀態篩選")
    status_filter = st.selectbox("廠商狀態篩選", sorted(ALLOWED_CONTACT_STATUSES), index=sorted(ALLOWED_CONTACT_STATUSES).index("new"))
    try:
        filtered_vendors = get_vendors_by_status(status_filter)
    except VendorOutreachError as error:
        show_error(error)
        filtered_vendors = pd.DataFrame()
    st.dataframe(filtered_vendors, use_container_width=True)

    if vendors.empty:
        st.info("目前沒有可產生開發信的廠商。")
    else:
        st.subheader("產生 / 寄送開發信")
        vendor_ids = [int(item) for item in pd.to_numeric(vendors["id"], errors="coerce").dropna()]
        selected_vendor_id = st.selectbox("廠商 ID", vendor_ids)
        template_type = st.selectbox("信件模板", ["initial", "follow_up"])
        if st.button("產生開發信"):
            try:
                email = generate_vendor_email(selected_vendor_id, template_type=template_type)
            except VendorOutreachError as error:
                show_error(error)
            else:
                st.text_input("信件主旨", value=email["subject"], key="vendor_email_subject")
                st.text_area("信件內容", value=email["body"], height=360, key="vendor_email_body")
                try:
                    update_vendor_status(selected_vendor_id, "email_drafted")
                except VendorOutreachError as error:
                    st.warning(f"提醒：{error}")
        if st.button("寄出 Email"):
            try:
                result = send_vendor_email(selected_vendor_id, template_type=template_type)
            except (EmailSenderError, VendorOutreachError) as error:
                show_error(error)
            else:
                st.success("Email 已寄出。")
                st.json(result)
                st.rerun()

    st.subheader("開發信紀錄")
    st.dataframe(email_log, use_container_width=True)


def show_seller_lead_tracker() -> None:
    st.header("賣家線索管理")
    try:
        leads = load_leads()
        new_leads = get_new_leads()
    except LeadTrackerError as error:
        show_error(error)
        return
    st.subheader("全部賣家線索")
    st.dataframe(leads, use_container_width=True)
    st.subheader("新線索")
    st.dataframe(new_leads, use_container_width=True)
    with st.form("add_seller_lead"):
        lead_date = st.date_input("線索日期", value=date.today())
        name = st.text_input("賣家名稱")
        source = st.text_input("來源", value="Facebook Page")
        equipment_type = st.text_input("設備類型", value="Vision Measuring Machine")
        brand = st.text_input("品牌")
        model = st.text_input("型號")
        location = st.text_input("設備所在地")
        contact_method = st.text_input("聯絡方式", value="LINE")
        contact_value = st.text_input("聯絡資訊")
        asking_price = st.text_input("開價")
        condition = st.text_area("設備狀況")
        status = st.selectbox("線索狀態", sorted(ALLOWED_LEAD_STATUSES), index=0)
        next_action = st.text_input("下一步動作")
        notes = st.text_area("備註")
        submitted = st.form_submit_button("新增線索")
    if submitted:
        try:
            lead_id = add_lead(lead_date.isoformat(), name, source, equipment_type, brand, model, location, contact_method, contact_value, asking_price, condition, status, next_action, notes)
        except LeadTrackerError as error:
            show_error(error)
        else:
            st.success(f"線索已新增：{lead_id}")
            st.rerun()
    if leads.empty:
        st.info("目前沒有可更新的賣家線索。")
        return
    ids = [int(item) for item in pd.to_numeric(leads["id"], errors="coerce").dropna()]
    with st.form("update_seller_lead_status"):
        lead_id = st.selectbox("線索 ID", ids)
        status = st.selectbox("新線索狀態", sorted(ALLOWED_LEAD_STATUSES), index=0)
        next_action = st.text_input("下一步動作", key="lead_next_action")
        notes = st.text_area("備註", key="lead_update_notes")
        submitted = st.form_submit_button("更新線索")
    if submitted:
        try:
            update_lead_status(lead_id, status, next_action=next_action, notes=notes)
        except LeadTrackerError as error:
            show_error(error)
        else:
            st.success(f"線索已更新：{lead_id}")
            st.rerun()


def show_metrics_tracker() -> None:
    st.header("成效追蹤")
    st.info("這裡只記錄人工成效數字。不會抓取 Facebook 資料，也不會呼叫外部 API。")
    try:
        metrics = load_metrics()
        summary = summarize_metrics()
    except MetricsTrackerError as error:
        show_error(error)
        return
    cols = st.columns(5)
    cols[0].metric("總曝光", summary["total_impressions"])
    cols[1].metric("總留言", summary["total_comments"])
    cols[2].metric("總私訊", summary["total_messages"])
    cols[3].metric("總線索", summary["total_leads"])
    cols[4].metric("已上架設備", summary["total_listed_items"])
    st.write("線索最多的平台：", summary["top_platform_by_leads"] or "N/A")
    st.write("線索最多的主題：", summary["top_topic_by_leads"] or "N/A")
    st.dataframe(metrics, use_container_width=True)
    with st.form("add_metric"):
        metric_date = st.date_input("成效日期", value=date.today())
        task_id = st.text_input("任務 ID")
        topic_id = st.text_input("主題 ID")
        platform = st.text_input("平台", value="Facebook Page")
        content_type = st.text_input("內容類型", value="Page Post")
        impressions = st.number_input("曝光數", min_value=0, step=1)
        reactions = st.number_input("反應數", min_value=0, step=1)
        comments = st.number_input("留言數", min_value=0, step=1)
        shares = st.number_input("分享數", min_value=0, step=1)
        clicks = st.number_input("點擊數", min_value=0, step=1)
        messages = st.number_input("私訊數", min_value=0, step=1)
        leads = st.number_input("線索數", min_value=0, step=1)
        listed_items = st.number_input("上架設備數", min_value=0, step=1)
        notes = st.text_area("成效備註")
        submitted = st.form_submit_button("新增成效")
    if submitted:
        try:
            metric_id = add_metric(metric_date.isoformat(), task_id, topic_id, platform, content_type, impressions, reactions, comments, shares, clicks, messages, leads, listed_items, notes)
        except MetricsTrackerError as error:
            show_error(error)
        else:
            st.success(f"成效紀錄已新增：{metric_id}")
            st.rerun()
    if metrics.empty:
        st.info("目前沒有可更新的成效紀錄。")
        return
    ids = [int(item) for item in pd.to_numeric(metrics["id"], errors="coerce").dropna()]
    with st.form("update_metric"):
        metric_id = st.selectbox("成效紀錄 ID", ids)
        impressions = st.number_input("更新曝光數", min_value=0, step=1)
        comments = st.number_input("更新留言數", min_value=0, step=1)
        messages = st.number_input("更新私訊數", min_value=0, step=1)
        leads = st.number_input("更新線索數", min_value=0, step=1)
        listed_items = st.number_input("更新上架設備數", min_value=0, step=1)
        notes = st.text_area("更新備註")
        submitted = st.form_submit_button("更新成效")
    if submitted:
        try:
            update_metric(metric_id, impressions=int(impressions), comments=int(comments), messages=int(messages), leads=int(leads), listed_items=int(listed_items), notes=notes)
        except MetricsTrackerError as error:
            show_error(error)
        else:
            st.success(f"成效紀錄已更新：{metric_id}")
            st.rerun()


load_dotenv(BASE_DIR / ".env")
st.set_page_config(page_title="ZeroGrav 冷啟動成長工作台 MVP", layout="wide")
st.title("ZeroGrav 冷啟動成長工作台 MVP")
st.caption("人工操作的冷啟動成長工作台。不會自動發布網站內容、不會自動操作 Facebook、不會自動寄信，也不會自動呼叫 OpenAI 或外部 API；只有在人員明確使用相關工具時才會執行。")

dataframes = {label: (filename, ensure_csv(path)) for label, (filename, path) in CSV_FILES.items()}
cols = st.columns(len(dataframes))
for col, (label, (_, df)) in zip(cols, dataframes.items()):
    col.metric(label, len(df))

with st.expander("資料表預覽", expanded=False):
    for _, (filename, df) in dataframes.items():
        st.subheader(filename)
        st.dataframe(df, use_container_width=True)

topics_df = dataframes["內容主題"][1]
with st.expander("每日冷啟動流程", expanded=True):
    show_daily_growth_workflow(topics_df)
with st.expander("產生內容 Prompt", expanded=False):
    show_prompt_generator(topics_df)
with st.expander("產生內容草稿", expanded=False):
    show_content_draft_generator(topics_df)
with st.expander("內容審稿清單", expanded=False):
    show_content_review_queue()
with st.expander("網站 / 社群內容匯出", expanded=False):
    show_website_social_content_exporter(topics_df)
with st.expander("發文任務管理", expanded=False):
    show_posting_task_manager()
with st.expander("廠商開發信助手", expanded=False):
    show_vendor_email_outreach_agent()
with st.expander("賣家線索管理", expanded=False):
    show_seller_lead_tracker()
with st.expander("成效追蹤", expanded=False):
    show_metrics_tracker()

# 安裝相關套件
import pandas as pd
import plotly.express as px

# 固定的欄位
DEFAULT_TASKS = pd.DataFrame(
    [
        {"task_code": "A", "task_name": "處理瑣事", "task_type": "sub", "required_count": 1},
        {"task_code": "B", "task_name": "文獻搜尋與書面報告", "task_type": "main", "required_count": 1},
        {"task_code": "C", "task_name": "簡報製作與口頭報告", "task_type": "sub", "required_count": 1},
    ]
)

DEFAULT_QUESTIONS = pd.DataFrame(
    [
        {"task_code": "A", "question_code": "A1", "question_text": "我願意負責會議記錄"},
        {"task_code": "A", "question_code": "A2", "question_text": "我願意負責主持會議"},
        {"task_code": "A", "question_code": "A3", "question_text": "我願意在群組中負責提醒進度或聯絡組員"},
        {"task_code": "B", "question_code": "B1", "question_text": "我願意做文獻搜尋與整理"},
        {"task_code": "B", "question_code": "B2", "question_text": "我願意寫書面報告及格式處理"},
        {"task_code": "C", "question_code": "C1", "question_text": "我願意做簡報（PPT / 視覺）"},
        {"task_code": "C", "question_code": "C2", "question_text": "我願意上台報告"},
    ]
)


def validate_task_requirements(tasks_df, member_count):
    errors = []
    if tasks_df.empty:
        errors.append("請至少設定一個工作")
        return errors, {}

    main_total = int(tasks_df[tasks_df["task_type"] == "main"]["required_count"].sum())
    sub_total = int(tasks_df[tasks_df["task_type"] == "sub"]["required_count"].sum())
    if main_total == 0:
        errors.append("請至少設定一個主工作 main")
    if sub_total == 0:
        errors.append("請至少設定一個副工作 sub")
    if member_count <= 0:
        errors.append("成員人數必須大於 0")
    else:
        if main_total % member_count != 0:
            errors.append("主工作總需求人次必須可以被成員人數整除")
        if sub_total % member_count != 0:
            errors.append("副工作總需求人次必須可以被成員人數整除")

    slots = {
        "main_slots_per_member": main_total // member_count if member_count and main_total % member_count == 0 else None,
        "sub_slots_per_member": sub_total // member_count if member_count and sub_total % member_count == 0 else None,
        "main_total": main_total,
        "sub_total": sub_total,
    }
    return errors, slots


def validate_ranks(rank_map, expected_task_codes):
    ranks = [int(rank_map[code]) for code in expected_task_codes]
    expected = list(range(1, len(expected_task_codes) + 1))
    if sorted(ranks) != expected:
        return False, f"排序必須剛好是 {expected}，不可重複或缺漏"
    return True, ""


def build_heatmap(scores_df, tasks_df, assignment_df, title):
    task_codes = tasks_df["task_code"].tolist()
    if scores_df.empty or not task_codes:
        return px.imshow(
            pd.DataFrame(),
            labels={"x": "工作向度", "y": "成員", "color": "動機分數"},
            color_continuous_scale="RdYlGn",
            zmin=1,
            zmax=5,
            title=title,
        )

    scores_df = scores_df.copy()
    scores_df["avg_score"] = pd.to_numeric(scores_df["avg_score"], errors="coerce")
    task_labels = {
        row["task_code"]: f"{row['task_code']} {row['task_name']}" for _, row in tasks_df.iterrows()
    }
    wide = scores_df.pivot_table(index="nickname", columns="task_code", values="avg_score", aggfunc="mean")
    wide = wide.reindex(columns=task_codes)

    assigned_pairs = set()
    if not assignment_df.empty:
        assigned_pairs = set(zip(assignment_df["nickname"], assignment_df["task_code"]))

    text = wide.copy().astype(object)
    for member in wide.index:
        for task_code in wide.columns:
            value = wide.loc[member, task_code]
            if pd.isna(value):
                text.loc[member, task_code] = ""
            elif (member, task_code) in assigned_pairs:
                text.loc[member, task_code] = f"★{value:.2f}"
            else:
                text.loc[member, task_code] = f"{value:.2f}"

    fig = px.imshow(
        wide.astype(float),
        text_auto=False,
        labels={"x": "工作向度", "y": "成員", "color": "動機分數"},
        color_continuous_scale="RdYlGn",
        zmin=1,
        zmax=5,
        title=title,
    )
    fig.update_traces(text=text.values, texttemplate="%{text}")
    fig.update_xaxes(ticktext=[task_labels[c] for c in wide.columns], tickvals=wide.columns.tolist())
    return fig


def summarize_missing_members(members_df, submitted_members):
    all_members = members_df["nickname"].tolist()
    return [member for member in all_members if member not in submitted_members]

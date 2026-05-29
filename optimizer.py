import numpy as np
import pandas as pd
from scipy.optimize import linear_sum_assignment


def preference_bonus(rank):
    if int(rank) == 1:
        return 2
    if int(rank) == 2:
        return 1
    return 0


def run_assignment(member_scores_df, preference_rank_df, task_requirements_df, task_type):
    tasks = task_requirements_df[task_requirements_df["task_type"] == task_type].copy()
    ranks = preference_rank_df[preference_rank_df["task_type"] == task_type].copy()
    if tasks.empty:
        return pd.DataFrame(), pd.DataFrame(), {"total_cost": 0, "first_choice_rate": 0}

    task_codes = tasks["task_code"].tolist()
    score_wide = member_scores_df.pivot_table(
        index="nickname", columns="task_code", values="avg_score", aggfunc="mean"
    )
    score_wide = score_wide.reindex(columns=task_codes)
    rank_wide = ranks.pivot_table(
        index="nickname", columns="task_code", values="rank", aggfunc="min"
    )
    rank_wide = rank_wide.reindex(index=score_wide.index, columns=task_codes)

    members = score_wide.index.tolist()
    total_slots = int(tasks["required_count"].sum())
    slots_per_member = total_slots // len(members)

    expanded_members = []
    for member in members:
        for slot_no in range(1, slots_per_member + 1):
            expanded_members.append({"expanded_member": f"{member}__{task_type}_{slot_no}", "nickname": member})

    expanded_slots = []
    for _, task in tasks.iterrows():
        for slot_no in range(1, int(task["required_count"]) + 1):
            expanded_slots.append(
                {
                    "slot_name": f"{task['task_code']}-{slot_no}",
                    "task_code": task["task_code"],
                    "task_name": task["task_name"],
                }
            )

    cost_matrix = np.zeros((len(expanded_members), len(expanded_slots)))
    for i, member_row in enumerate(expanded_members):
        member = member_row["nickname"]
        s_max = score_wide.loc[member, task_codes].max()
        for j, slot in enumerate(expanded_slots):
            task_code = slot["task_code"]
            score = score_wide.loc[member, task_code]
            rank = rank_wide.loc[member, task_code]
            if pd.isna(score) or pd.isna(rank):
                cost = 9999
            else:
                cost = float(s_max) - float(score) - preference_bonus(rank)
            cost_matrix[i, j] = cost

    row_ind, col_ind = linear_sum_assignment(cost_matrix)
    rows = []
    for row_index, col_index in zip(row_ind, col_ind):
        member = expanded_members[row_index]["nickname"]
        task_code = expanded_slots[col_index]["task_code"]
        rows.append(
            {
                "nickname": member,
                "task_code": task_code,
                "task_name": expanded_slots[col_index]["task_name"],
                "task_type": task_type,
                "slot_name": expanded_slots[col_index]["slot_name"],
                "motivation_score": float(score_wide.loc[member, task_code]),
                "preference_rank": int(rank_wide.loc[member, task_code]),
                "cost": float(cost_matrix[row_index, col_index]),
            }
        )

    assignment_df = pd.DataFrame(rows).sort_values(["nickname", "task_code", "slot_name"])
    cost_matrix_df = pd.DataFrame(
        cost_matrix,
        index=[row["expanded_member"] for row in expanded_members],
        columns=[row["slot_name"] for row in expanded_slots],
    )

    summary = {
        "task_type": task_type,
        "total_cost": float(assignment_df["cost"].sum()),
        "first_choice_rate": float((assignment_df["preference_rank"] == 1).mean()),
        "avg_motivation_score": float(assignment_df["motivation_score"].mean()),
        "min_motivation_score": float(assignment_df["motivation_score"].min()),
        "slots_per_member": int(slots_per_member),
    }
    return assignment_df, cost_matrix_df, summary


def combine_assignment_tables(main_assignment_df, sub_assignment_df, tasks_df):
    members = sorted(
        set(main_assignment_df.get("nickname", pd.Series(dtype=str)).tolist())
        | set(sub_assignment_df.get("nickname", pd.Series(dtype=str)).tolist())
    )
    rows = []
    for member in members:
        main_rows = main_assignment_df[main_assignment_df["nickname"] == member]
        sub_rows = sub_assignment_df[sub_assignment_df["nickname"] == member]
        rows.append(
            {
                "成員": member,
                "主工作": _join_tasks(main_rows),
                "主工作動機分數": _join_values(main_rows, "motivation_score"),
                "主工作排序/偏好": _join_values(main_rows, "preference_rank"),
                "副工作": _join_tasks(sub_rows),
                "副工作動機分數": _join_values(sub_rows, "motivation_score"),
                "副工作排序/偏好": _join_values(sub_rows, "preference_rank"),
            }
        )
    return pd.DataFrame(rows)


def _join_tasks(df):
    if df.empty:
        return ""
    return "、".join((df["task_code"] + " " + df["task_name"]).tolist())


def _join_values(df, column):
    if df.empty:
        return ""
    values = []
    for value in df[column].tolist():
        if column == "motivation_score":
            values.append(f"{value:.2f}")
        else:
            values.append(str(int(value)))
    return "、".join(values)

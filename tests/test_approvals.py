"""
test_approvals.py
=================
覆盖主管审批的核心能力：
  A. 单条审批 (single)
     1. 成功 approve — 状态变 approved + 审批历史落表
     2. 成功 reject  — 状态变 rejected + 审批历史落表
     3. 失败路径：未知工时ID -> 404
     4. 失败路径：未知审批人 -> 404
     5. 失败路径：审批人不是员工的主管（无 admin 权限） -> 403
     6. 失败路径：重复审批 already approved -> 400
     7. 失败路径：非法 action（非 approved/rejected） -> 400
     8. admin 角色可以审批任意员工 -> 200

  B. 批量审批 (bulk)
     1. 全部 processed 成功：返回 processed_ids，状态正确
     2. mixed processed + skipped（部分记录已审批过）
     3. skipped：另一个主管的下属
     4. failed：包含不存在的工时ID
     5. 失败路径：审批人角色非法 -> 403

  C. 审批历史查询
     1. /history/{ts_id} 返回完整的审批时间线
     2. /approver/{id} 按审批人查看审批记录
"""
from datetime import date

import pytest


WORKDAY = date(2030, 3, 12)


def _submit_ts(client, emp_id: int, workday=WORKDAY, hours: float = 8, tag: str = "TEST"):
    """辅助函数：快速提交一条 pending 工时，返回创建后的 JSON"""
    resp = client.post(
        "/api/v1/timesheets",
        json={
            "employee_id": emp_id,
            "date": workday.isoformat(),
            "hours": hours,
            "project_tag": tag,
        },
    )
    assert resp.status_code == 201
    return resp.json()


# ============================================================================
#  A. 单条审批
# ============================================================================
class TestSingleApprovalSuccess:
    def test_single_approved_updates_status_and_creates_history(
        self, client, supervisor, employee
    ):
        ts = _submit_ts(client, employee.id)
        resp = client.post(
            "/api/v1/approvals/single",
            json={
                "timesheet_id": ts["id"],
                "approver_id": supervisor.id,
                "action": "approved",
                "comment": "完成质量高",
            },
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == "approved"

        # 审批历史落表
        history = client.get(f"/api/v1/approvals/history/{ts['id']}").json()
        assert len(history) == 1
        assert history[0]["action"] == "approved"
        assert history[0]["approver_id"] == supervisor.id
        assert history[0]["comment"] == "完成质量高"

    def test_single_rejected_updates_status(self, client, supervisor, employee):
        ts = _submit_ts(client, employee.id)
        resp = client.post(
            "/api/v1/approvals/single",
            json={
                "timesheet_id": ts["id"],
                "approver_id": supervisor.id,
                "action": "rejected",
                "comment": "需要补充项目明细",
            },
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == "rejected"
        history = client.get(f"/api/v1/approvals/history/{ts['id']}").json()
        assert history[0]["action"] == "rejected"


class TestSingleApprovalFailures:
    def test_unknown_timesheet_returns_404(self, client, supervisor):
        resp = client.post(
            "/api/v1/approvals/single",
            json={
                "timesheet_id": 99999,
                "approver_id": supervisor.id,
                "action": "approved",
            },
        )
        assert resp.status_code == 404

    def test_unknown_approver_returns_404(self, client, employee):
        ts = _submit_ts(client, employee.id)
        resp = client.post(
            "/api/v1/approvals/single",
            json={"timesheet_id": ts["id"], "approver_id": 9999, "action": "approved"},
        )
        assert resp.status_code == 404

    def test_non_supervisor_role_returns_403(self, client, employee, employee_b):
        """普通员工（role=employee）不具备审批权限"""
        ts = _submit_ts(client, employee_b.id)
        resp = client.post(
            "/api/v1/approvals/single",
            json={"timesheet_id": ts["id"], "approver_id": employee.id, "action": "approved"},
        )
        assert resp.status_code == 403

    def test_wrong_supervisor_returns_403(self, client, employee, other_supervisor):
        """不是自己的主管不能审批"""
        ts = _submit_ts(client, employee.id)
        resp = client.post(
            "/api/v1/approvals/single",
            json={
                "timesheet_id": ts["id"],
                "approver_id": other_supervisor.id,
                "action": "approved",
            },
        )
        assert resp.status_code == 403

    def test_double_approval_returns_400(self, client, supervisor, employee):
        """重复审批 -> 400"""
        ts = _submit_ts(client, employee.id)
        client.post(
            "/api/v1/approvals/single",
            json={"timesheet_id": ts["id"], "approver_id": supervisor.id, "action": "approved"},
        )
        resp = client.post(
            "/api/v1/approvals/single",
            json={"timesheet_id": ts["id"], "approver_id": supervisor.id, "action": "approved"},
        )
        assert resp.status_code == 400
        assert "already" in resp.json()["detail"]

    def test_invalid_action_returns_400(self, client, supervisor, employee):
        """action 拼写错误"""
        ts = _submit_ts(client, employee.id)
        resp = client.post(
            "/api/v1/approvals/single",
            json={"timesheet_id": ts["id"], "approver_id": supervisor.id, "action": "ACCEPT"},
        )
        assert resp.status_code == 400

    def test_admin_can_approve_any_employee(self, client, employee_b, admin):
        """admin 角色不受 supervisor_id 限制"""
        ts = _submit_ts(client, employee_b.id)
        resp = client.post(
            "/api/v1/approvals/single",
            json={"timesheet_id": ts["id"], "approver_id": admin.id, "action": "approved"},
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == "approved"


# ============================================================================
#  B. 批量审批
# ============================================================================
class TestBulkApprovalGroups:
    def test_all_processed(self, client, supervisor, employee):
        """5 条 pending 全部 rejected -> processed 5 条"""
        ids = [_submit_ts(client, employee.id, hours=i + 1)["id"] for i in range(5)]
        resp = client.post(
            "/api/v1/approvals/bulk",
            json={
                "timesheet_ids": ids,
                "approver_id": supervisor.id,
                "action": "rejected",
                "comment": "批量驳回",
            },
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["total"] == 5
        assert body["processed_count"] == 5
        assert body["skipped_count"] == 0 and body["failed_count"] == 0
        assert sorted(body["processed"]) == sorted(ids)

    def test_mixed_processed_and_skipped_already_approved(
        self, client, supervisor, employee
    ):
        """3条中1条提前批准 -> processed=2 skipped=1"""
        ids = [_submit_ts(client, employee.id)["id"] for _ in range(3)]
        # 把 ids[1] 提前批准
        client.post(
            "/api/v1/approvals/single",
            json={"timesheet_id": ids[1], "approver_id": supervisor.id, "action": "approved"},
        )
        resp = client.post(
            "/api/v1/approvals/bulk",
            json={
                "timesheet_ids": ids,
                "approver_id": supervisor.id,
                "action": "rejected",
            },
        )
        body = resp.json()
        assert body["processed_count"] == 2
        assert body["skipped_count"] == 1
        assert ids[1] in body["skipped"]
        assert ids[0] in body["processed"] and ids[2] in body["processed"]

    def test_skipped_wrong_supervisor_and_fake_ids(
        self, client, supervisor, employee, other_supervisor, employee_b
    ):
        """
        processed = 员工A的2条（是supervisor的下属）
        skipped   = 员工B的1条（不是supervisor的下属）
        failed    = 99999 不存在
        """
        good_ids = [_submit_ts(client, employee.id)["id"] for _ in range(2)]
        other_id = _submit_ts(client, employee_b.id)["id"]  # employee_b 的主管是 supervisor（fixture中是）
        # 注意：fixture 里 employee_b.supervisor_id == supervisor.id，所以这里需要用 other_supervisor 再创建下属
        # 手动插入一个不归 supervisor 管的下属
        from app.models import User
        from tests.conftest import TestingSessionLocal

        s = TestingSessionLocal()
        rogue = User(
            employee_id="EMP-ROGUE",
            name="独立员工",
            email="rogue@test.com",
            role="employee",
            supervisor_id=other_supervisor.id,
        )
        s.add(rogue)
        s.commit()
        s.refresh(rogue)
        rogue_id = rogue.id
        s.close()

        rogue_ts = _submit_ts(client, rogue_id)["id"]
        fake_id = 99999

        ids = good_ids + [rogue_ts, fake_id]
        resp = client.post(
            "/api/v1/approvals/bulk",
            json={
                "timesheet_ids": ids,
                "approver_id": supervisor.id,
                "action": "approved",
            },
        )
        body = resp.json()
        assert body["total"] == 4
        assert body["processed_count"] == 2
        assert set(body["processed"]) == set(good_ids)
        assert body["skipped_count"] == 1
        assert rogue_ts in body["skipped"]
        assert body["failed_count"] == 1
        assert fake_id in body["failed"]

    def test_bulk_invalid_approver_role_returns_403(self, client, employee):
        ids = [_submit_ts(client, employee.id)["id"]]
        resp = client.post(
            "/api/v1/approvals/bulk",
            json={
                "timesheet_ids": ids,
                "approver_id": employee.id,  # 是员工不是主管
                "action": "approved",
            },
        )
        assert resp.status_code == 403


# ============================================================================
#  C. 审批历史查询
# ============================================================================
class TestApprovalHistory:
    def test_history_chronological(self, client, supervisor, admin, employee):
        """同一工时被2次操作（先reject后approve不可能，但此处两次用不同action演示多个history记录）
        注意：实际接口不允许重复审批，因此创建两条工时，查看主管的审批列表。
        """
        ts_a = _submit_ts(client, employee.id)
        ts_b = _submit_ts(client, employee.id)
        client.post(
            "/api/v1/approvals/single",
            json={"timesheet_id": ts_a["id"], "approver_id": supervisor.id, "action": "approved"},
        )
        client.post(
            "/api/v1/approvals/single",
            json={"timesheet_id": ts_b["id"], "approver_id": supervisor.id, "action": "rejected"},
        )
        # 按审批人查看历史
        approver_hist = client.get(f"/api/v1/approvals/approver/{supervisor.id}").json()
        actions = [h["action"] for h in approver_hist]
        assert len(approver_hist) == 2
        assert "approved" in actions and "rejected" in actions

    def test_unknown_timesheet_history_404(self, client):
        resp = client.get("/api/v1/approvals/history/99999")
        assert resp.status_code == 404

    def test_unknown_approver_history_404(self, client):
        resp = client.get("/api/v1/approvals/approver/99999")
        assert resp.status_code == 404

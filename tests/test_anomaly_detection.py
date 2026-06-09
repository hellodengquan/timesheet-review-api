"""
test_anomaly_detection.py
=========================
覆盖 anomaly 自动检测的核心逻辑：
  1. 单条工时 <12h，非假日 -> 无 anomaly
  2. 第一条 8h + 第二条 5h -> 当日累计 13h，第二条自动 anomaly
  3. 工作在法定假日（非 >12h 也触发）-> anomaly
  4. 非假日且累计 =12h 刚好 -> 不触发 anomaly
  5. 异常查询接口 /api/v1/anomalies 能正确过滤出带 anomaly 的记录
  6. 工时更新（PUT）后累计超阈值 -> 重新触发 anomaly 检测
"""
from datetime import date

import pytest


class TestNormalNoAnomaly:
    """普通场景：单条 8h、非假日，不应带 anomaly"""

    def test_single_normal_workday_no_anomaly(self, client, employee, workday_date):
        resp = client.post(
            "/api/v1/timesheets",
            json={
                "employee_id": employee.id,
                "date": workday_date.isoformat(),
                "hours": 8,
                "project_tag": "PROJ-NORMAL",
                "description": "标准工作日8小时",
            },
        )
        assert resp.status_code == 201
        body = resp.json()
        assert "anomaly" not in body["tags"].split(",")
        assert body["status"] == "pending"

    def test_exactly_12h_not_triggered(self, client, employee, workday_date):
        """累计 =12h 刚好，不触发 (>12 才触发)"""
        r1 = client.post(
            "/api/v1/timesheets",
            json={
                "employee_id": employee.id,
                "date": workday_date.isoformat(),
                "hours": 7,
                "project_tag": "A",
            },
        )
        r2 = client.post(
            "/api/v1/timesheets",
            json={
                "employee_id": employee.id,
                "date": workday_date.isoformat(),
                "hours": 5,
                "project_tag": "B",
            },
        )
        assert r1.status_code == 201
        assert r2.status_code == 201
        tags_r2 = [t for t in r2.json()["tags"].split(",") if t]
        assert "anomaly" not in tags_r2


class TestDailyHoursExceed12:
    """日累计 > 12h 触发 anomaly"""

    def test_second_submission_triggers_anomaly(self, client, employee, workday_date):
        """第一条 8h（正常） + 第二条 5h（累计13h） -> 第二条带 anomaly"""
        r1 = client.post(
            "/api/v1/timesheets",
            json={
                "employee_id": employee.id,
                "date": workday_date.isoformat(),
                "hours": 8,
                "project_tag": "A",
            },
        )
        r2 = client.post(
            "/api/v1/timesheets",
            json={
                "employee_id": employee.id,
                "date": workday_date.isoformat(),
                "hours": 5,
                "project_tag": "B",
            },
        )
        assert r1.status_code == 201 and r2.status_code == 201

        r1_tags = [t for t in r1.json()["tags"].split(",") if t]
        r2_tags = [t for t in r2.json()["tags"].split(",") if t]

        assert "anomaly" not in r1_tags, "第一条没超阈值不应 anomaly"
        assert "anomaly" in r2_tags, "第二条累计超阈值必须 anomaly"

    def test_single_over_12h_immediate_anomaly(self, client, employee, workday_date):
        """单条直接 >12h -> 提交时立即 anomaly"""
        resp = client.post(
            "/api/v1/timesheets",
            json={
                "employee_id": employee.id,
                "date": workday_date.isoformat(),
                "hours": 13,
                "project_tag": "LONG",
            },
        )
        assert resp.status_code == 201
        tags = [t for t in resp.json()["tags"].split(",") if t]
        assert "anomaly" in tags

    def test_three_records_cumulative_trigger(self, client, employee, workday_date):
        """5 + 5 + 3 = 13，第三条触发"""
        client.post("/api/v1/timesheets", json={"employee_id": employee.id, "date": workday_date.isoformat(), "hours": 5, "project_tag": "A"})
        client.post("/api/v1/timesheets", json={"employee_id": employee.id, "date": workday_date.isoformat(), "hours": 5, "project_tag": "B"})
        r3 = client.post(
            "/api/v1/timesheets",
            json={"employee_id": employee.id, "date": workday_date.isoformat(), "hours": 3, "project_tag": "C"},
        )
        tags = [t for t in r3.json()["tags"].split(",") if t]
        assert "anomaly" in tags

    def test_different_employees_not_crossed(self, client, employee, employee_b, workday_date):
        """不同员工的当日累计互不影响"""
        client.post("/api/v1/timesheets", json={"employee_id": employee.id, "date": workday_date.isoformat(), "hours": 10, "project_tag": "A"})
        r_emp_b = client.post(
            "/api/v1/timesheets",
            json={"employee_id": employee_b.id, "date": workday_date.isoformat(), "hours": 8, "project_tag": "B"},
        )
        tags = [t for t in r_emp_b.json()["tags"].split(",") if t]
        assert "anomaly" not in tags, "员工A的工时不应该计入员工B"


class TestHolidayHitAnomaly:
    """法定假日 -> 任何工时都自动 anomaly"""

    def test_holiday_submission_auto_anomaly(self, client, employee, seeded_holiday, holiday_date):
        """即使只有 2h，在假日当天也自动 anomaly"""
        resp = client.post(
            "/api/v1/timesheets",
            json={
                "employee_id": employee.id,
                "date": holiday_date.isoformat(),
                "hours": 2,
                "project_tag": "SUPPORT",
                "description": "假日值班",
            },
        )
        assert resp.status_code == 201
        tags = [t for t in resp.json()["tags"].split(",") if t]
        assert "anomaly" in tags

    def test_holiday_plus_over_12h_only_one_anomaly_tag(self, client, employee, seeded_holiday, holiday_date):
        """假日 + >12h -> anomaly 只出现一次（去重）"""
        resp = client.post(
            "/api/v1/timesheets",
            json={
                "employee_id": employee.id,
                "date": holiday_date.isoformat(),
                "hours": 13,
                "project_tag": "SUPPORT",
            },
        )
        assert resp.status_code == 201
        tags = [t for t in resp.json()["tags"].split(",") if t]
        assert tags.count("anomaly") == 1


class TestAnomalyQueryEndpoint:
    """测试 /api/v1/anomalies 查询接口"""

    def _submit(self, client, emp_id, d, h, tag):
        return client.post(
            "/api/v1/timesheets",
            json={"employee_id": emp_id, "date": d, "hours": h, "project_tag": tag},
        ).json()

    def test_anomaly_list_filtering(self, client, employee, workday_date, seeded_holiday, holiday_date):
        """2条正常 + 1条超阈值 + 1条假日 -> anomalies 接口应返回 2 条"""
        self._submit(client, employee.id, workday_date.isoformat(), 4, "N1")
        self._submit(client, employee.id, workday_date.isoformat(), 4, "N2")
        self._submit(client, employee.id, workday_date.isoformat(), 5, "OVER")  # 累计 13 -> anomaly
        self._submit(client, employee.id, holiday_date.isoformat(), 2, "HOLIDAY")

        resp = client.get("/api/v1/anomalies")
        assert resp.status_code == 200
        body = resp.json()
        assert body["total"] == 2
        returned_tags = [t for it in body["items"] for t in it["tags"].split(",") if t]
        assert all(t == "anomaly" for t in returned_tags)

    def test_anomaly_filter_by_employee(self, client, employee, employee_b, workday_date):
        """按员工ID过滤 anomaly"""
        # 员工A：超阈值
        client.post("/api/v1/timesheets", json={"employee_id": employee.id, "date": workday_date.isoformat(), "hours": 14, "project_tag": "A"})
        # 员工B：正常
        client.post("/api/v1/timesheets", json={"employee_id": employee_b.id, "date": workday_date.isoformat(), "hours": 6, "project_tag": "B"})

        resp = client.get(f"/api/v1/anomalies?employee_id={employee.id}")
        body = resp.json()
        assert resp.status_code == 200
        assert body["total"] == 1
        assert body["items"][0]["employee_id"] == employee.id

        resp_b = client.get(f"/api/v1/anomalies?employee_id={employee_b.id}")
        assert resp_b.json()["total"] == 0


class TestUpdateTriggersRecheck:
    """工时更新 (PUT) 后需要重新做 anomaly 检测"""

    def test_put_increase_hours_over_threshold(self, client, employee, workday_date):
        """先提交 5h（正常），然后 PUT 改成 13h -> 变 anomaly"""
        create_resp = client.post(
            "/api/v1/timesheets",
            json={"employee_id": employee.id, "date": workday_date.isoformat(), "hours": 5, "project_tag": "T"},
        )
        ts_id = create_resp.json()["id"]
        assert "anomaly" not in create_resp.json()["tags"]

        update_resp = client.put(
            f"/api/v1/timesheets/{ts_id}",
            json={"hours": 13},
        )
        assert update_resp.status_code == 200
        tags = [t for t in update_resp.json()["tags"].split(",") if t]
        assert "anomaly" in tags

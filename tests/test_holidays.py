"""
test_holidays.py
================
覆盖法定假日配置的 CRUD（成功与失败路径）：
  1. POST 新增假日成功 (201)
  2. POST 重复日期 -> 400
  3. GET 列表查询：按 start_date / end_date 范围过滤
  4. DELETE 成功 (204)
  5. DELETE 不存在 id -> 404
  6. 新增假日后，当日报工自动 anomaly（联动验证，确保 CRUD 与 anomaly 链路打通）
"""

from datetime import date

import pytest

HOLIDAY_DATE = date(2030, 10, 1)
ANOTHER_DATE = date(2030, 10, 2)
FAR_FUTURE = date(2099, 1, 1)


# ============================================================================
#  POST 新增
# ============================================================================
class TestHolidayCreate:
    def test_create_success_201(self, client):
        resp = client.post(
            "/api/v1/anomalies/holidays",
            json={"date": HOLIDAY_DATE.isoformat(), "name": "国庆节"},
        )
        assert resp.status_code == 201
        body = resp.json()
        assert body["date"] == HOLIDAY_DATE.isoformat()
        assert body["name"] == "国庆节"
        assert "id" in body

    def test_create_duplicate_date_returns_400(self, client, seeded_holiday, holiday_date):
        """同日期重复插入 -> 400"""
        resp = client.post(
            "/api/v1/anomalies/holidays",
            json={"date": holiday_date.isoformat(), "name": "重名节日"},
        )
        assert resp.status_code == 400
        assert "already exists" in resp.json()["detail"]

    def test_create_invalid_payload_missing_name(self, client):
        resp = client.post(
            "/api/v1/anomalies/holidays",
            json={"date": HOLIDAY_DATE.isoformat()},
        )
        # Pydantic 校验失败 -> 422
        assert resp.status_code == 422

    def test_create_invalid_payload_bad_date_format(self, client):
        resp = client.post(
            "/api/v1/anomalies/holidays",
            json={"date": "2030/10/01", "name": "X"},
        )
        assert resp.status_code == 422


# ============================================================================
#  GET 查询
# ============================================================================
class TestHolidayList:
    def test_list_empty(self, client):
        resp = client.get("/api/v1/anomalies/holidays")
        assert resp.status_code == 200
        assert resp.json() == []

    def test_list_returns_seeded(self, client, seeded_holiday, holiday_date):
        resp = client.get("/api/v1/anomalies/holidays")
        body = resp.json()
        assert resp.status_code == 200
        assert len(body) == 1
        assert body[0]["date"] == holiday_date.isoformat()

    def test_list_date_range_filter(self, client):
        """插入 3 个日期，按范围过滤 -> 只返回范围内 2 个"""
        dates = [date(2030, 5, 1), date(2030, 5, 15), date(2030, 6, 1)]
        for i, d in enumerate(dates):
            client.post(
                "/api/v1/anomalies/holidays",
                json={"date": d.isoformat(), "name": f"节日{i}"},
            )
        resp = client.get(
            "/api/v1/anomalies/holidays",
            params={"start_date": "2030-05-01", "end_date": "2030-05-31"},
        )
        body = resp.json()
        assert len(body) == 2
        returned = [b["date"] for b in body]
        assert "2030-05-01" in returned and "2030-05-15" in returned
        assert "2030-06-01" not in returned

    def test_list_pagination(self, client):
        for i in range(5):
            client.post(
                "/api/v1/anomalies/holidays",
                json={"date": date(2030, 1, i + 1).isoformat(), "name": f"H{i}"},
            )
        resp = client.get("/api/v1/anomalies/holidays?skip=2&limit=2")
        body = resp.json()
        assert len(body) == 2


# ============================================================================
#  DELETE 删除
# ============================================================================
class TestHolidayDelete:
    def test_delete_success_204(self, client, seeded_holiday):
        resp = client.delete(f"/api/v1/anomalies/holidays/{seeded_holiday.id}")
        assert resp.status_code == 204
        # 再查一次确认没有了
        remaining = client.get("/api/v1/anomalies/holidays").json()
        assert len(remaining) == 0

    def test_delete_unknown_id_404(self, client):
        resp = client.delete("/api/v1/anomalies/holidays/999999")
        assert resp.status_code == 404


# ============================================================================
#  链路验证：假日CRUD 与 anomaly 检测联动
# ============================================================================
class TestHolidayLinkedToAnomaly:
    def test_after_add_holiday_timesheet_gets_anomaly(self, client, employee):
        the_date = date(2030, 11, 11)
        # 先在普通日报工：无 anomaly
        before = client.post(
            "/api/v1/timesheets",
            json={
                "employee_id": employee.id,
                "date": the_date.isoformat(),
                "hours": 3,
                "project_tag": "BEFORE",
            },
        ).json()
        assert "anomaly" not in before["tags"].split(",")

        # 把该日期设为假日
        client.post(
            "/api/v1/anomalies/holidays",
            json={"date": the_date.isoformat(), "name": "双11购物节"},
        )

        # 再在同一日报工：自动 anomaly
        after = client.post(
            "/api/v1/timesheets",
            json={
                "employee_id": employee.id,
                "date": the_date.isoformat(),
                "hours": 2,
                "project_tag": "AFTER",
            },
        ).json()
        tags = [t for t in after["tags"].split(",") if t]
        assert "anomaly" in tags

    def test_after_delete_holiday_timesheet_no_longer_anomaly(self, client, employee, holiday_date):
        # 先加假日
        client.post(
            "/api/v1/anomalies/holidays",
            json={"date": holiday_date.isoformat(), "name": "临时假日"},
        )
        with_holiday = client.post(
            "/api/v1/timesheets",
            json={
                "employee_id": employee.id,
                "date": holiday_date.isoformat(),
                "hours": 3,
                "project_tag": "HOL",
            },
        ).json()
        assert "anomaly" in with_holiday["tags"].split(",")

        # 查出假日 id 并删除
        holidays = client.get("/api/v1/anomalies/holidays").json()
        hid = holidays[0]["id"]
        client.delete(f"/api/v1/anomalies/holidays/{hid}")

        # 再在同日提交（累计没超12h）：不再 anomaly
        after_del = client.post(
            "/api/v1/timesheets",
            json={
                "employee_id": employee.id,
                "date": holiday_date.isoformat(),
                "hours": 2,
                "project_tag": "AFTER_DEL",
            },
        ).json()
        tags = [t for t in after_del["tags"].split(",") if t]
        assert "anomaly" not in tags

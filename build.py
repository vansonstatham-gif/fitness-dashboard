"""Generate the training & goals dashboard from Feishu Bases.

Usage:  python dashboard/build.py
Output: dashboard/index.html  (+ data.json for debugging)
"""
import json
import os
import subprocess
import sys
from collections import defaultdict
from datetime import date, datetime, timedelta

RUN = r"C:/Users/Vanson Statham/AppData/Roaming/npm/node_modules/@larksuite/cli/scripts/run.js"
HERE = os.path.dirname(os.path.abspath(__file__))

TRAIN = ("HEHObJrrGaZkzGsuLqkcO4nTnPc", "tbljBJ1bAn4KFfQY")
DIET = ("BOcdbX7ePa6g70sjUHBc5U2znWh", "tblNAJud7qEGnn99")
HEALTH_BASE = "Xn5pbjfdfaZSIXszj6hcOHqpnQh"
BODY = (HEALTH_BASE, "tbljdBtnThbVlCuW")
ACT = (HEALTH_BASE, "tbldTZ5iBxskugMP")
RINGS = (HEALTH_BASE, "tblLIQp8ZENEpPmZ")

FAT_LINE = 1800
FAT_LINE_TRAIN = 1900
PROTEIN_TARGET = 130

GOALS = {"卧推": 140, "深蹲": 210, "硬拉": 210}
FAT_TARGET = 15.0
WEIGHT_LO, WEIGHT_HI = 65, 70


def run(args):
    return subprocess.run(
        ["node", RUN] + args + ["--profile", "fitness-coach", "--as", "user"],
        capture_output=True, text=True, encoding="utf-8", errors="replace",
        creationflags=0x08000000,
    )


def s(v):
    if v is None:
        return ""
    if isinstance(v, list):
        return ",".join(s(x) for x in v)
    if isinstance(v, dict):
        return v.get("text") or v.get("value") or json.dumps(v, ensure_ascii=False)
    return str(v)


def num(v, default=None):
    try:
        if v is None or v == "":
            return default
        return float(v)
    except (TypeError, ValueError):
        return default


def day(v):
    return s(v)[:10]


def fetch(base_token, table_id):
    out = os.path.join(HERE, f"_tmp_{table_id}.ndjson")
    r = run(["base", "+record-list", "--base-token", base_token, "--table-id", table_id,
             "--sort-json", json.dumps([{"field": "日期", "desc": True}], ensure_ascii=False),
             "--limit", "2000", "--format", "ndjson"])
    if r.returncode != 0:
        raise RuntimeError(f"record-list {table_id} failed: {r.stderr[-300:]}")
    mani = json.loads(r.stdout[r.stdout.index("{"):])
    rows = [json.loads(l) for l in open(mani["record_file"], encoding="utf-8") if l.strip()]
    for f in (out, mani["record_file"], mani["record_file"][:-7] + ".manifest.json",
              mani["record_file"] + ".manifest.json"):
        try:
            os.remove(f)
        except OSError:
            pass
    return rows


PART_RULES = [
    ("硬拉", ("硬拉", "DEADLIFT", "DEAD LIFT")),
    ("RDL", ("RDL", "罗马尼亚")),
    ("腿", ("深蹲", "SQUAT", "LEG PRESS", "腿屈伸", "腿弯举", "GLUTE", "臀推", "小腿", "LUNGE", "蹬腿")),
    ("有氧", ("爬楼", "单车", "跑步", "游泳", "ROWING", "椭圆", "快走", "爬坡")),
    ("背", ("引体", "ROW", "划船", "下拉", "LAT PULL", "PULLDOWN", "PULL UP", "PULLUP", "PULL-UP", "高位下拉")),
    ("胸", ("卧推", "BENCH", "CHEST", "INCLINE", "PEC", "蝴蝶", "夹胸", "飞鸟", "FLY", "FLIGHT", "俯卧撑")),
    ("肩", ("实力举", "侧平举", "面拉", "LATERAL", "DELTOID", "SHOULDER", "肩推", "推举")),
]


def part_of(name):
    n = (name or "").upper()
    for part, keys in PART_RULES:
        if any(k in n for k in keys):
            return part
    return "其他"


def main():
    today = date.today()
    tr_rows = fetch(*TRAIN)
    diet_rows = fetch(*DIET)
    body_rows = fetch(*BODY)
    act_rows = fetch(*ACT)
    ring_rows = fetch(*RINGS)

    # ---------- training ----------
    lifts = defaultdict(list)
    by_date = defaultdict(lambda: {"sets": 0, "volume": 0.0, "items": defaultdict(list), "parts": set()})
    for x in tr_rows:
        d = day(x.get("日期"))
        name = s(x.get("动作")).strip()
        w = num(x.get("实际重量"), 0) or 0
        reps = num(x.get("次数"), 0) or 0
        vol = num(x.get("容量"), 0) or 0
        if not d or not name:
            continue
        item = by_date[d]
        item["sets"] += 1
        item["volume"] += vol
        item["parts"].add(part_of(name))
        item["items"][name].append((w, reps))

        if w > 0 and reps > 0:
            e1rm = w * (1 + reps / 30)
            lifts[name].append((d, w, reps, e1rm))

    cutoff_90 = (today - timedelta(days=90)).isoformat()

    def best_e1rm(name):
        rows = lifts.get(name, [])
        if not rows:
            return None, None, None
        recent = [r for r in rows if r[0] >= cutoff_90] or rows
        r = max(recent, key=lambda t: t[3])
        return r[3], r[1], r[2]

    goals = []
    for lift, target in GOALS.items():
        e, w, reps = best_e1rm(lift)
        if e is None:
            goals.append({"name": lift, "current": "无记录", "target": f"{target}kg", "pct": 0, "cls": "warn"})
            continue
        goals.append({
            "name": lift,
            "current": f"e1RM {e:.0f}kg ({w:.0f}×{reps:.0f})",
            "target": f"{target}kg",
            "pct": e / target * 100,
            "cls": "warn" if e / target < 0.6 else "",
            "note": f"还差 {max(0, target - e):.0f}kg",
        })

    # body fat / weight goals
    body_sorted = sorted([r for r in body_rows if day(r.get("日期"))], key=lambda r: day(r.get("日期")))
    bf_now = wt_now = None
    if body_sorted:
        last = body_sorted[-1]
        bf_now = num(last.get("体脂率"))
        wt_now = num(last.get("体重"))
        last_body_date = day(last.get("日期"))
    # baseline = first reading on/after the goal plan start (2026-08-01)
    plan_start = "2026-08-01"
    base_rows = [r for r in body_sorted if day(r.get("日期")) >= plan_start] or body_sorted
    base_bf = num(base_rows[0].get("体脂率")) if base_rows else None
    base_wt = num(base_rows[0].get("体重")) if base_rows else None
    if bf_now:
        pct = ((base_bf - bf_now) / (base_bf - FAT_TARGET) * 100) if base_bf and base_bf > FAT_TARGET else 100
        delta = bf_now - base_bf if base_bf else 0
        goals.append({"name": "体脂率", "current": f"{bf_now:.1f}%", "target": f"{FAT_TARGET:.0f}%",
                      "pct": max(0, pct), "cls": "warn" if pct < 30 else "",
                      "note": (f"起点 {base_bf:.1f}%，已{'上升' if delta>0 else '下降'} {abs(delta):.1f} 个点"
                               if base_bf else f"还差 {max(0, bf_now - FAT_TARGET):.1f} 个点")})
    if wt_now:
        if wt_now <= WEIGHT_HI:
            pct = 100
        elif base_wt and base_wt > WEIGHT_HI:
            pct = max(0, min(99, (base_wt - wt_now) / (base_wt - WEIGHT_HI) * 100))
        else:
            pct = 0
        goals.append({"name": "体重", "current": f"{wt_now:.1f}kg", "target": f"{WEIGHT_LO}-{WEIGHT_HI}kg",
                      "pct": pct, "cls": "" if wt_now <= WEIGHT_HI else "warn",
                      "note": f"距 {WEIGHT_LO}kg 还差 {max(0, wt_now - WEIGHT_LO):.1f}kg"})

    # ---------- gaps ----------
    last_seen = defaultdict(str)
    for d, item in by_date.items():
        for p in item["parts"]:
            if d > last_seen[p]:
                last_seen[p] = d
    gaps = []
    for p in ["胸", "背", "肩", "腿", "硬拉", "RDL"]:
        ls = last_seen.get(p)
        days = (today - datetime.strptime(ls, "%Y-%m-%d").date()).days if ls else None
        gaps.append({"name": p, "days": days, "last": ls})

    # ---------- diet / health by date ----------
    diet_by_date = defaultdict(lambda: {"kcal": 0.0, "protein": 0.0, "items": []})
    for x in diet_rows:
        d = day(x.get("日期"))
        if not d:
            continue
        rec = diet_by_date[d]
        k = num(x.get("教练估算·热量(kcal)"), 0) or 0
        p = num(x.get("教练估算·蛋白质(g)"), 0) or 0
        rec["kcal"] += k
        rec["protein"] += p
        rec["items"].append({"time": s(x.get("餐点")), "food": s(x.get("食物")), "kcal": k, "protein": p})

    act_by_date = {}
    for x in act_rows:
        d = day(x.get("日期"))
        if d:
            act_by_date[d] = x
    ring_by_date = {}
    for x in ring_rows:
        d = day(x.get("日期"))
        if d:
            ring_by_date[d] = x

    last_health_date = max(act_by_date) if act_by_date else None
    health = act_by_date.get(today.isoformat()) or (act_by_date.get(last_health_date) if last_health_date else None) or {}
    hdate = day(health.get("日期")) if health else None

    # ---------- today ----------
    td = today.isoformat()
    td_tr = by_date.get(td, {"sets": 0, "volume": 0.0, "items": {}, "parts": set()})
    td_diet = diet_by_date.get(td, {"kcal": 0.0, "protein": 0.0, "items": []})
    items = []
    for name, pairs in td_tr["items"].items():
        w = max(p[0] for p in pairs)
        reps = [p[1] for p in pairs if p[0] == w]
        items.append({"name": name, "sets": f"{w:.0f}×{reps[0]:.0f}" + (f"×{len(pairs)}" if len(pairs) > 1 else ""),
                      "volume": sum(a * b for a, b in pairs)})
    items.sort(key=lambda i: -i["volume"])

    today_summary = {
        "training": {
            "sets": td_tr["sets"], "volume": td_tr["volume"],
            "parts": " / ".join(sorted(td_tr["parts"])) if td_tr["parts"] else "休息日",
            "items": items,
        },
        "diet": {"kcal": td_diet["kcal"], "protein": td_diet["protein"],
                 "line": FAT_LINE_TRAIN if td_tr["sets"] else FAT_LINE,
                 "protein_target": PROTEIN_TARGET},
        "health": {
            "sleep": num(health.get("睡眠时长")),
            "steps": num(health.get("步数")),
            "active": num(health.get("活动能量")),
            "date": hdate,
        },
    }

    # ---------- 14-day series ----------
    series = []
    for i in range(13, -1, -1):
        d = (today - timedelta(days=i)).isoformat()
        series.append({
            "date": d,
            "volume": round(by_date.get(d, {"volume": 0})["volume"]),
            "kcal": round(diet_by_date.get(d, {"kcal": 0})["kcal"]),
            "protein": round(diet_by_date.get(d, {"protein": 0})["protein"]),
            "sleep": round(num((act_by_date.get(d) or {}).get("睡眠时长"), 0) or 0, 2),
        })

    # ---------- recent sessions ----------
    sessions = []
    for d in sorted(by_date, reverse=True)[:6]:
        item = by_date[d]
        top = max(item["items"].items(), key=lambda kv: sum(a * b for a, b in kv[1]))[0] if item["items"] else "—"
        sessions.append({"date": d, "parts": " / ".join(sorted(item["parts"])),
                         "sets": item["sets"], "volume": round(item["volume"]), "top": top})

    data = {
        "today": td,
        "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "phase": "减脂期 · 目标体脂 15%",
        "goals": goals,
        "gaps": gaps,
        "todaySummary": today_summary,
        "series": series,
        "sessions": sessions,
        "lastHealthDate": hdate,
        "rings": {
            "active": num((ring_by_date.get(hdate) or {}).get("活动能量")),
            "active_goal": num((ring_by_date.get(hdate) or {}).get("活动目标")),
            "move": num((ring_by_date.get(hdate) or {}).get("运动分钟")),
            "move_goal": num((ring_by_date.get(hdate) or {}).get("运动目标")),
            "stand": num((ring_by_date.get(hdate) or {}).get("站立小时")),
            "stand_goal": num((ring_by_date.get(hdate) or {}).get("站立目标")),
        },
    }

    with open(os.path.join(HERE, "data.json"), "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    tpl = open(os.path.join(HERE, "template.html"), encoding="utf-8").read()
    html = tpl.replace("__DATA_JSON__", json.dumps(data, ensure_ascii=False))
    with open(os.path.join(HERE, "index.html"), "w", encoding="utf-8") as f:
        f.write(html)

    print(f"ok: index.html written | today={td} | training {td_tr['sets']} sets "
          f"{td_tr['volume']:.0f}kg | diet {td_diet['kcal']:.0f}/{td_diet['protein']:.0f}g")


if __name__ == "__main__":
    sys.exit(main())

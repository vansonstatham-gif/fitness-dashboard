# Vanson · 训练 & 目标看板

个人训练/饮食/健康总览，数据来自飞书多维表格（训练 Base、饮食 Base、苹果健康 Base）。

## 目标（2026-08-17 设定）

| 项目 | 目标 |
|---|---|
| 体重 | 65–70kg |
| 体脂率 | 15% |
| 卧推 | 140kg @70kg |
| 深蹲 | 210kg |
| 硬拉 | 210kg |

## 本地重建

```bash
python build.py
```

会拉取三个 Base 的最新数据，重新生成 `index.html`（内嵌数据，单文件即可打开）。

需要本机已登录 `lark-cli`（profile: fitness-coach）。

## 自动更新

每晚定时任务执行 `build.py` → commit → push，GitHub Pages 自动刷新。

## 文件

- `build.py` — 拉数据 + 计算指标 + 渲染
- `template.html` — 页面模板（深色，移动端适配）
- `index.html` — 生成产物（GitHub Pages 入口）
- `data.json` — 生成的数据快照

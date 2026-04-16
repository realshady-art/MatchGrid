# Match Board（战术板）

在浏览器里用 **自由坐标** 摆主客队阵容，基于本地球员赛季指标做 **主胜 / 平局 / 客胜** 的启发式估算。界面为 **Slock 式新粗野主义** 外壳 + **实况（PES）风格** 球场与棋子展示。

> **声明**：预测逻辑为演示用启发式，**不是**博彩盘口或商业模型，请勿用于实际投注决策。

---

## 功能说明

| 能力 | 说明 |
|------|------|
| **双队战术板** | 从侧栏 roster 拖球员上场；棋子可在场内任意移动；拖出草皮或双击棋子可移除。 |
| **离线优先** | 核心页面与预测在本地完成；球员名单来自已生成的数据文件，无需实时调用付费 API。 |
| **五大联赛池** | 通过公开 Understat 接口拉取联赛数据，生成 `players_pool.csv` / 同步 JSON，含搜索与按联赛筛选。 |
| **球员指数** | 在本地为每名球员计算简化的 **atk / def / gk** 等维度，用于 `board_predict` 估算双方强度差。 |
| **结果条** | 根据当前场上双方阵容与坐标，调用 `/api/board/predict` 更新 H/D/A 比例与说明文案。 |
| **头像** | 优先使用 **TheSportsDB** 官方球员 **cutout / thumb**（职业剪影式定妆图），按俱乐部名辅助消歧；极少数无数据时再回退维基缩略图。缓存为 `{球员id}_pro.png|jpg`（`static/player_photos/`，图片默认不提交仓库）。升级后若仍见旧图，可删掉该目录下旧的 `*.jpg`（无 `_pro` 后缀）后刷新。 |
| **路由** | 仅保留战术板：`/` 为主页，`/board` 重定向到 `/`。 |

---

## 技术栈

- **后端**：Python 3、Flask  
- **数据**：pandas、requests（抓取 Understat）  
- **前端**：原生 HTML/CSS/JS（`board.js` 指针拖拽、侧栏列表）

---

## 环境与安装

推荐使用虚拟环境：

```bash
python3 -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

若未装依赖就运行 `main.py gui`，会出现 `No module named 'flask'` 等错误，请先执行 `pip install`。

---

## 数据准备（需联网，建议执行一次）

生成 `data/board/players_pool.csv` 并同步打包用的球员 JSON（具体路径由 `src/board_data.py` / 脚本约定）：

```bash
python3 main.py fetch-board-data
```

`data/` 目录默认被 `.gitignore` 忽略，克隆仓库后需要本地自行拉取或拷贝数据。

---

## 启动应用

```bash
python3 main.py gui
```

默认监听 **http://127.0.0.1:5000/** 。

若本机 **5000** 被占用（例如 macOS 相关服务），可换端口：

```bash
python3 main.py gui --port 5055
```

浏览器打开对应地址即可。

可选环境变量 **`THESPORTSDB_API_KEY`**：默认使用 TheSportsDB 公开开发用 key；若请求频繁可在 [thesportsdb.com](https://www.thesportsdb.com/api.php) 申请自有 key 后设置。

---

## HTTP API（摘要）

| 方法 | 路径 | 作用 |
|------|------|------|
| `GET` | `/` | 战术板页面 |
| `GET` | `/api/board/players` | 查询参数：`q`、`league`、`limit` — 返回可拖拽球员列表 |
| `POST` | `/api/board/predict` | JSON body：`home` / `away` 为 `{ player_id, x, y }[]`，返回概率与元信息 |
| `GET` | `/api/board/player-photo/<player_id>` | 返回缓存的球员头像图片 |

---

## 仓库结构（主要文件）

```
main.py                 # 子命令：gui、fetch-board-data
scripts/build_players_pool.py
src/
  gui_app.py            # Flask 应用与路由
  board_data.py         # 读 roster、过滤、联赛标签
  board_indices.py      # atk/def/gk 等指数
  board_predict.py      # 阵容 vs 阵容启发式
  understat_fetch.py    # Understat 抓取辅助
  player_photos.py      # 维基头像缓存
  config.py
static/
  styles.css            # Slock 全局变量与基础组件
  board.css / board.js  # 球场与交互
  shell.js              # 顶栏时钟等
templates/
  base.html
  match_board.html
```

---

## 许可与致谢

球员统计数据来源请遵循 **Understat** 的使用条款与版权声明；维基媒体头像遵循各自图片许可。

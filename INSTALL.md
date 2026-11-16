# 安装与接入

## 前置条件

- Python 3.10+
- 依赖：`pip install -r requirements.txt`
- PandaData 账号（仅在需要现拉数据时使用）

## 通用步骤

```bash
git clone https://github.com/quantskills/skill-q2-roll-cta.git
cd skill-q2-roll-cta
pip install -r requirements.txt
python scripts/test.py
```

凭据通过环境变量注入，不写入代码或仓库：

```bash
# Windows cmd
set PANDA_DATA_USERNAME=your_phone
set PANDA_DATA_PASSWORD=your_password
set PANDA_DATA_BASE_URL=http://pandadata.pandaaiquant.com

# macOS / Linux
export PANDA_DATA_USERNAME=your_phone
export PANDA_DATA_PASSWORD=your_password
export PANDA_DATA_BASE_URL=http://pandadata.pandaaiquant.com
```

## Claude Code

把仓库放到项目的 `.claude/skills/roll-cta/`，或直接在当前目录读取 `SKILL.md`：

```text
.claude/skills/roll-cta/
├── SKILL.md
├── scripts/
└── references/
```

## Codex

在项目根目录保留 `SKILL.md`，Codex 会按仓库内 skill 发现规则读取。运行入口：

```bash
python scripts/build.py --data-dir /path/to/data
```

## Cursor

把仓库复制到 `.cursor/skills/roll-cta/`，并加载 `agents/cursor-rule.mdc`。

## Hermes / OpenClaw

使用 `agents/portable-loader.md` 中的提示词，把 `<ROLL_CTA_SKILL_ROOT>` 替换为本地仓库绝对路径。

## 验证

```bash
python scripts/test.py
python scripts/build.py --data-dir /path/to/data --rules fixed
```

`tests/fixtures/` 已带真实数据切片，测试无需 PandaData 凭据。

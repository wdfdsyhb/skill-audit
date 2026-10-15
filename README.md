# skill-audit

[![CI](https://github.com/wdfdsyhb/skill-audit/actions/workflows/tests.yml/badge.svg)](https://github.com/wdfdsyhb/skill-audit/actions/workflows/tests.yml)

**Audit AI agent skill libraries** — frontmatter lint, duplicate detection, and the always-on token cost of your whole library. For Claude Code / ZCode / Codex-style `<skill>/SKILL.md` directories.

体检你的 AI 技能库：元数据合规、重复技能、以及全库的常驻 token 成本。

## Why

技能是按 `~name + description` 常驻在模型上下文里的。装 300 个技能，每次会话还没开始就先烧掉几万 token；同名技能互相覆盖、描述雷同的技能让路由乱跳——这些没人看得见，直到出问题。skill-audit 把它们变成一份报告。

## Checks

- **frontmatter 合规**：缺 name / 缺 description / description 超长 / 空正文
- **name 一致性**：frontmatter 里的 `name:` 是否和目录名一致（改名忘改配置是常态）
- **重复检测**：同名技能（硬重复）+ 描述相似度 >= 0.80 的疑似重复（先用词集预筛，600+ 技能也是秒级）
- **token 成本**：每个技能的常驻元数据 ≈ 多少 token，全库合计

## Usage

```bash
python skill_audit.py ~/.zcode/skills            # 全量报告
python skill_audit.py ./skills -q                # 只看有问题的
python skill_audit.py ./skills --json report.json
python skill_audit.py ./skills --index INDEX.md  # 生成全库索引
```

输出示例：

```
[ok]                                                       45 tok  C:\...\.zcode\skills\src-hunter\SKILL.md
[missing description (this is what the model routes on)]    8 tok  C:\...\.zcode\skills\old-skill\SKILL.md
[DUPE SAME NAME] grilling
    C:\...\.zcode\skills\grilling\SKILL.md
    C:\...\.zcode\skills\mattpocock\grilling\SKILL.md
[..duplicate groups..]

623 skills | issues on 41 | 3 duplicate groups | always-on metadata ~= 28410 tokens
```

发现问题时退出码为 1，可以接 CI。

## Notes

- frontmatter 解析只支持扁平 `key: value`（嵌套 YAML 字段忽略），这是 SKILL.md 标准里路由实际用到的部分
- token 估算是 4 字符/token 的启发式，看趋势够用，别拿去做账单
- 零第三方依赖，纯标准库

## License

MIT

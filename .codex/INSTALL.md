# Installing Yoke for Codex

通过 Codex 原生 skill 发现机制安装 Yoke。克隆仓库并创建符号链接即可。

## 前置条件

- Git
- OpenAI Codex CLI

## 安装

1. **克隆仓库：**
   ```bash
   git clone git@github.com:<your-org>/yoke.git ~/.codex/yoke
   ```

2. **创建 skills 符号链接：**
   ```bash
   mkdir -p ~/.agents/skills
   ln -s ~/.codex/yoke/skills ~/.agents/skills/yoke
   ```

3. **重启 Codex** 使 skills 生效。

## 验证

```bash
ls -la ~/.agents/skills/yoke
```

应该看到指向 `~/.codex/yoke/skills/` 的符号链接。

## 更新

```bash
cd ~/.codex/yoke && git pull
```

通过符号链接即时生效。

## 卸载

```bash
rm ~/.agents/skills/yoke
```

可选删除克隆：`rm -rf ~/.codex/yoke`

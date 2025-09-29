# 文章标签处理工具

这是一个使用OpenAI API为文章自动生成标签的工具。

## 功能特性

- 自动读取指定目录下的文章文件（支持.txt、.md、.json格式）
- 支持从JSON文件中提取文章内容，可指定内容字段
- 使用OpenAI API为每篇文章生成3-5个中文标签
- 维护全局标签池，统计标签出现次数
- 支持热门标签分析和统计
- 支持多线程并行处理，提高处理效率
- 线程安全，避免重复处理同一文件
- 提供详细的处理进度和统计信息

## 安装依赖

```bash
pip install -e .
```

或者手动安装依赖：

```bash
pip install openai python-dotenv tqdm
```

## 配置

1. 复制 `.env.example` 到 `.env` 文件
2. 在 `.env` 文件中配置你的OpenAI API密钥：

```env
OPENAI_API_KEY=your_openai_api_key_here
OPENAI_BASE_URL=https://api.openai.com/v1
OPENAI_MODEL=gpt-3.5-turbo
MAX_WORKERS=4
OUTPUT_FILE=tags.json
DATA_DIR=post-tags/data
```

## 使用方法

### 基本用法

```bash
python post-tags/process-post.py
```

### 指定参数

```bash
# 使用8个工作线程
python post-tags/process-post.py --workers 8

# 指定输出文件
python post-tags/process-post.py --output my_tags.json

# 指定数据目录
python post-tags/process-post.py --data-dir /path/to/articles

# 预览模式（只显示要处理的文件，不实际处理）
python post-tags/process-post.py --dry-run

# 显示详细日志
python post-tags/process-post.py --verbose

# 显示详细标签统计
python post-tags/process-post.py --show-stats

# 检查JSON文件结构
python post-tags/process-post.py --inspect-json

# 指定JSON文件中的内容字段
python post-tags/process-post.py --content-field content

# 启用增量保存（每处理一篇文章就保存一次）
python post-tags/process-post.py --content-field content --incremental-save
```

### 参数说明

- `--workers, -w`: 并行处理的工作线程数（默认：4）
- `--output, -o`: 输出文件路径（默认：tags.json）
- `--data-dir, -d`: 数据目录路径（默认：post-tags/data）
- `--dry-run`: 预览模式，只显示要处理的文件
- `--verbose, -v`: 显示详细日志信息
- `--show-stats`: 显示详细的标签统计信息
- `--content-field, -f`: 指定JSON文件中要读取的内容字段名
- `--inspect-json`: 检查JSON文件结构，显示可用的字段名
- `--incremental-save`: 启用增量保存，每处理一篇文章就保存一次结果

### 调试和故障排除

如果处理失败，可以：

1. **使用详细日志模式**：
   ```bash
   python post-tags/process-post.py --verbose
   ```

2. **查看日志文件**：
   程序会生成 `process_post.log` 文件，包含详细的处理日志

3. **运行测试脚本**：
   ```bash
   python test_process.py
   ```

4. **检查常见问题**：
   - 确保 `.env` 文件存在且配置正确
   - 确保OpenAI API密钥有效
   - 确保数据目录存在且包含文章文件
   - 检查网络连接和API配额

## JSON文件支持

工具支持从JSON文件中读取文章内容，支持以下格式：

### 1. JSON数组格式
```json
[
  {
    "content": "文章内容1",
    "title": "标题1",
    "author": "作者1"
  },
  {
    "content": "文章内容2", 
    "title": "标题2",
    "author": "作者2"
  }
]
```

### 2. 单个JSON对象格式
```json
{
  "content": "文章内容",
  "title": "标题",
  "author": "作者"
}
```

### 3. 使用方法

1. **检查JSON文件结构**：
   ```bash
   python post-tags/process-post.py --inspect-json
   ```

2. **指定内容字段**：
   ```bash
   # 如果内容在 'content' 字段中
   python post-tags/process-post.py --content-field content
   
   # 如果内容在 'text' 字段中
   python post-tags/process-post.py --content-field text
   ```

3. **自动字段检测**：
   如果不指定字段，工具会自动尝试以下字段名：
   - `content`
   - `text`
   - `body`
   - `description`

## 输出格式

处理完成后，会生成两个JSON文件：

### 1. 标签列表文件 (tags.json)
包含所有标签的列表（按字母顺序排序）：

```json
[
  "人工智能",
  "机器学习",
  "深度学习",
  "神经网络",
  "算法"
]
```

### 2. 标签统计文件 (tags_stats.json)
包含标签的详细统计信息：

```json
{
  "total_tags": 13,
  "total_occurrences": 15,
  "tag_counts": {
    "人工智能": 2,
    "机器学习": 1,
    "深度学习": 2,
    "神经网络": 1
  },
  "top_tags": {
    "人工智能": 2,
    "深度学习": 2,
    "机器学习": 1,
    "神经网络": 1
  }
}
```

## 多线程处理

工具支持多线程并行处理，可以显著提高处理速度。注意事项：

1. **线程安全**：使用锁机制确保标签池的线程安全更新
2. **避免重复处理**：使用文件锁确保同一文件不会被重复处理
3. **进度显示**：使用tqdm显示实时处理进度
4. **错误处理**：单个文件处理失败不会影响其他文件的处理

## 示例

```bash
# 处理默认目录下的文章
python post-tags/process-post.py

# 使用8个线程处理，输出到custom_tags.json
python post-tags/process-post.py --workers 8 --output custom_tags.json

# 预览要处理的文件
python post-tags/process-post.py --dry-run
```

## 注意事项

1. 确保OpenAI API密钥有效且有足够的配额
2. 文章内容会被截断到3000字符以内，以控制API调用成本
3. 生成的标签都是中文标签，长度不限
4. 建议根据API配额和网络情况调整工作线程数

#!/usr/bin/env python3
"""
文章标签处理脚本
功能：读取data目录下的文章文件，使用OpenAI生成两字标签，并整合到标签池中
"""
import argparse
import json
import logging
import os
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import List, Set, Dict, Any
from collections import Counter
import time

import openai
from tqdm import tqdm

from settings import settings
from prompt import prompt

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('process_post.log', encoding='utf-8')
    ]
)
logger = logging.getLogger(__name__)


class TagProcessor:
    """标签处理器"""
    
    def __init__(self):
        self.client = openai.OpenAI(
            api_key=settings.openai_api_key,
            base_url=settings.openai_base_url
        )
        self.tag_pool: Set[str] = set()
        self.tag_counter: Counter = Counter()  # 标签计数器
        self.tag_lock = threading.Lock()
        self.processed_files: Set[str] = set()
        self.file_lock = threading.Lock()
        self.processed_articles: Set[str] = set()  # 已处理的文章ID
    
    def read_article(self, file_path: str, content_field: str = None) -> str:
        """读取文章内容（单个文件）"""
        try:
            logger.info(f"开始读取文件: {file_path}")
            
            # 检查文件扩展名
            file_ext = Path(file_path).suffix.lower()
            
            if file_ext == '.json':
                # 处理JSON文件
                with open(file_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                
                if isinstance(data, dict):
                    # 如果是单个对象
                    if content_field and content_field in data:
                        content = str(data[content_field]).strip()
                    else:
                        # 尝试常见的字段名
                        for field in ['content', 'text', 'body', 'description']:
                            if field in data:
                                content = str(data[field]).strip()
                                break
                        else:
                            logger.error(f"JSON文件中未找到内容字段")
                            return ""
                else:
                    logger.error(f"JSON文件应该是单个对象，但得到: {type(data)}")
                    return ""
            else:
                # 处理普通文本文件
                with open(file_path, 'r', encoding='utf-8') as f:
                    content = f.read().strip()
            
            logger.info(f"成功读取文件 {file_path}，内容长度: {len(content)} 字符")
            return content
        except Exception as e:
            logger.error(f"读取文件 {file_path} 失败: {e}")
            return ""
    
    def read_json_articles(self, file_path: str, content_field: str = None) -> List[Dict[str, Any]]:
        """读取JSON文件中的所有文章"""
        try:
            logger.info(f"开始读取JSON文件: {file_path}")
            
            with open(file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            if not isinstance(data, list):
                logger.error(f"JSON文件应该是数组格式，但得到: {type(data)}")
                return []
            
            articles = []
            for i, item in enumerate(data):
                if isinstance(item, dict):
                    # 提取内容字段
                    if content_field and content_field in item:
                        content = str(item[content_field]).strip()
                    else:
                        # 如果没有指定字段，尝试常见的字段名
                        for field in ['content', 'text', 'body', 'description']:
                            if field in item:
                                content = str(item[field]).strip()
                                break
                        else:
                            logger.warning(f"JSON数组第{i}项未找到内容字段")
                            continue
                    
                    if content:
                        articles.append({
                            'index': i,
                            'content': content,
                            'metadata': {k: v for k, v in item.items() if k != content_field}
                        })
                        logger.info(f"提取第{i+1}篇文章，内容长度: {len(content)} 字符")
            
            logger.info(f"成功读取JSON文件，共提取 {len(articles)} 篇文章")
            return articles
        except Exception as e:
            logger.error(f"读取JSON文件 {file_path} 失败: {e}")
            return []
    
    def load_state(self, output_file: str) -> bool:
        """加载之前的状态"""
        try:
            # 加载标签池
            if os.path.exists(output_file):
                with open(output_file, 'r', encoding='utf-8') as f:
                    tag_list = json.load(f)
                self.tag_pool = set(tag_list)
                logger.info(f"加载了 {len(self.tag_pool)} 个现有标签")
            
            # 加载标签统计
            stats_file = output_file.replace('.json', '_stats.json')
            if os.path.exists(stats_file):
                with open(stats_file, 'r', encoding='utf-8') as f:
                    stats_data = json.load(f)
                self.tag_counter = Counter(stats_data.get('tag_counts', {}))
                logger.info(f"加载了标签统计，总出现次数: {sum(self.tag_counter.values())}")
            
            # 加载已处理文章记录
            progress_file = output_file.replace('.json', '_progress.json')
            if os.path.exists(progress_file):
                with open(progress_file, 'r', encoding='utf-8') as f:
                    progress_data = json.load(f)
                self.processed_files = set(progress_data.get('processed_files', []))
                self.processed_articles = set(progress_data.get('processed_articles', []))
                logger.info(f"加载了处理进度: {len(self.processed_files)} 个文件, {len(self.processed_articles)} 篇文章")
            
            return True
        except Exception as e:
            logger.error(f"加载状态失败: {e}")
            return False
    
    def save_state(self, output_file: str) -> None:
        """保存当前状态"""
        try:
            # 保存处理进度
            progress_file = output_file.replace('.json', '_progress.json')
            progress_data = {
                'processed_files': list(self.processed_files),
                'processed_articles': list(self.processed_articles),
                'last_update': time.strftime('%Y-%m-%d %H:%M:%S')
            }
            with open(progress_file, 'w', encoding='utf-8') as f:
                json.dump(progress_data, f, ensure_ascii=False, indent=2)
            logger.info(f"状态已保存到: {progress_file}")
        except Exception as e:
            logger.error(f"保存状态失败: {e}")
    
    def generate_tags(self, content: str) -> List[str]:
        """使用OpenAI生成文章标签"""
        if not content:
            logger.warning("内容为空，无法生成标签")
            return []
        
        try:
            logger.info(f"开始调用OpenAI API生成标签，内容长度: {len(content)}")
            logger.debug(f"使用模型: {settings.openai_model}")
            
            response = self.client.chat.completions.create(
                model=settings.openai_model,
                messages=[
                    {
                        "role": "system",
                        "content": prompt
                    },
                    {
                        "role": "user",
                        "content": f"请为以下文章生成标签：\n\n{content[:3000]}"  # 限制内容长度
                    }
                ],
                max_tokens=100,
                temperature=0.7
            )
            
            tags_text = response.choices[0].message.content.strip()
            logger.info(f"OpenAI API响应: {tags_text}")
            
            # 解析标签 - 支持多种分隔符
            # 先按逗号分割，然后处理每个标签
            raw_tags = []
            for tag_part in tags_text.split(','):
                tag_part = tag_part.strip()
                if tag_part:
                    # 如果标签包含井号，按井号进一步分割
                    if '#' in tag_part:
                        # 提取井号内的内容
                        import re
                        hashtag_matches = re.findall(r'#([^#]+)#', tag_part)
                        raw_tags.extend(hashtag_matches)
                        # 也保留井号外的内容
                        non_hashtag = re.sub(r'#[^#]*#', '', tag_part).strip()
                        if non_hashtag:
                            raw_tags.append(non_hashtag)
                    else:
                        raw_tags.append(tag_part)
            
            # 清理和过滤标签
            tags = []
            for tag in raw_tags:
                tag = tag.strip()
                if tag and len(tag) >= 2:
                    # 移除多余的标点符号
                    tag = tag.strip('，。！？；：""''（）【】《》')
                    if tag and len(tag) >= 2:
                        tags.append(tag)
            
            logger.info(f"解析出的原始标签: {raw_tags}")
            logger.info(f"过滤后的有效标签: {tags}")
            
            final_tags = tags[:5]  # 最多返回5个标签
            logger.info(f"最终生成的标签: {final_tags}")
            return final_tags
            
        except openai.APIError as e:
            logger.error(f"OpenAI API错误: {e}")
            return []
        except openai.RateLimitError as e:
            logger.error(f"OpenAI API速率限制: {e}")
            return []
        except openai.AuthenticationError as e:
            logger.error(f"OpenAI API认证失败: {e}")
            return []
        except Exception as e:
            logger.error(f"生成标签时发生未知错误: {e}")
            return []
    
    def process_single_article(self, article: Dict[str, Any], file_name: str, output_file: str = None, incremental_save: bool = False) -> Dict[str, Any]:
        """处理单篇文章"""
        article_id = f"{file_name}#{article['index']}"
        
        # 检查是否已处理过
        if article_id in self.processed_articles:
            logger.info(f"文章 {article_id} 已经处理过，跳过")
            return {"article": article_id, "status": "skipped", "reason": "already_processed"}
        
        logger.info(f"开始处理文章: {article_id}")
        
        content = article['content']
        if not content:
            logger.error(f"文章 {article_id} 内容为空")
            return {"article": article_id, "status": "failed", "reason": "empty_content"}
        
        # 生成标签
        logger.info(f"开始为文章 {article_id} 生成标签")
        tags = self.generate_tags(content)
        if not tags:
            logger.error(f"文章 {article_id} 未能生成任何标签")
            return {"article": article_id, "status": "failed", "reason": "no_tags_generated"}
        
        # 更新标签池和计数器
        with self.tag_lock:
            old_size = len(self.tag_pool)
            self.tag_pool.update(tags)
            self.tag_counter.update(tags)  # 更新标签计数
            new_size = len(self.tag_pool)
            added_tags = new_size - old_size
            logger.info(f"文章 {article_id} 生成了 {len(tags)} 个标签，新增 {added_tags} 个到标签池")
            logger.info(f"标签计数更新: {dict(self.tag_counter.most_common(5))}")  # 显示前5个最热标签
            
            # 实时保存标签池
            if output_file and incremental_save:
                self.save_tags_incremental(output_file)
                self.save_state(output_file)
        
        # 记录已处理
        self.processed_articles.add(article_id)
        
        logger.info(f"文章 {article_id} 处理成功")
        return {
            "article": article_id,
            "status": "success",
            "tags": tags,
            "content_length": len(content),
            "metadata": article.get('metadata', {})
        }
    
    def process_single_file(self, file_path: str, content_field: str = None, output_file: str = None, incremental_save: bool = False) -> Dict[str, Any]:
        """处理单个文件"""
        file_name = os.path.basename(file_path)
        logger.info(f"开始处理文件: {file_name}")
        
        # 检查是否已处理过
        with self.file_lock:
            if file_path in self.processed_files:
                logger.warning(f"文件 {file_name} 已经处理过，跳过")
                return {"file": file_name, "status": "skipped", "reason": "already_processed"}
        
        # 检查文件类型
        file_ext = Path(file_path).suffix.lower()
        
        if file_ext == '.json':
            # 处理JSON文件，提取所有文章
            articles = self.read_json_articles(file_path, content_field)
            if not articles:
                logger.error(f"文件 {file_name} 中未找到有效文章")
                return {"file": file_name, "status": "failed", "reason": "no_valid_articles"}
            
            # 处理每篇文章
            results = []
            for article in articles:
                result = self.process_single_article(article, file_name, output_file, incremental_save)
                results.append(result)
            
            # 统计结果
            success_count = sum(1 for r in results if r["status"] == "success")
            failed_count = sum(1 for r in results if r["status"] == "failed")
            skipped_count = sum(1 for r in results if r["status"] == "skipped")
            
            # 记录文件已处理
            with self.file_lock:
                self.processed_files.add(file_path)
            
            logger.info(f"文件 {file_name} 处理完成: 成功 {success_count} 篇，失败 {failed_count} 篇，跳过 {skipped_count} 篇")
            return {
                "file": file_name,
                "status": "success",
                "articles_processed": len(articles),
                "articles_success": success_count,
                "articles_failed": failed_count,
                "articles_skipped": skipped_count,
                "results": results
            }
        else:
            # 处理普通文本文件
            content = self.read_article(file_path, content_field)
            if not content:
                logger.error(f"文件 {file_name} 内容为空")
                return {"file": file_name, "status": "failed", "reason": "empty_content"}
            
            # 生成标签
            logger.info(f"开始为文件 {file_name} 生成标签")
            tags = self.generate_tags(content)
            if not tags:
                logger.error(f"文件 {file_name} 未能生成任何标签")
                return {"file": file_name, "status": "failed", "reason": "no_tags_generated"}
            
            # 更新标签池和计数器
            with self.tag_lock:
                old_size = len(self.tag_pool)
                self.tag_pool.update(tags)
                self.tag_counter.update(tags)  # 更新标签计数
                new_size = len(self.tag_pool)
                added_tags = new_size - old_size
                logger.info(f"文件 {file_name} 生成了 {len(tags)} 个标签，新增 {added_tags} 个到标签池")
                logger.info(f"标签计数更新: {dict(self.tag_counter.most_common(5))}")  # 显示前5个最热标签
            
            logger.info(f"文件 {file_name} 处理成功")
            return {
                "file": file_name,
                "status": "success",
                "tags": tags,
                "content_length": len(content)
            }
    
    def process_files(self, file_paths: List[str], max_workers: int = 4, content_field: str = None, output_file: str = None, incremental_save: bool = False) -> List[Dict[str, Any]]:
        """处理多个文件"""
        results = []
        
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            # 提交所有任务
            future_to_file = {
                executor.submit(self.process_single_file, file_path, content_field, output_file, incremental_save): file_path 
                for file_path in file_paths
            }
            
            # 使用tqdm显示进度
            with tqdm(total=len(file_paths), desc="处理文章") as pbar:
                for future in as_completed(future_to_file):
                    try:
                        result = future.result()
                        results.append(result)
                        pbar.update(1)
                        
                        # 显示处理状态
                        if result["status"] == "success":
                            if "articles_processed" in result:
                                pbar.set_postfix({
                                    "当前文件": result["file"],
                                    "处理文章": result["articles_success"],
                                    "标签池大小": len(self.tag_pool)
                                })
                            else:
                                pbar.set_postfix({
                                    "当前文件": result["file"],
                                    "生成标签": len(result.get("tags", [])),
                                    "标签池大小": len(self.tag_pool)
                                })
                        else:
                            pbar.set_postfix({
                                "当前文件": result["file"],
                                "状态": result["status"]
                            })
                    except Exception as e:
                        logger.error(f"处理文件时发生错误: {e}")
                        results.append({
                            "file": "unknown",
                            "status": "failed",
                            "reason": str(e)
                        })
                        pbar.update(1)
        
        return results
    
    def save_tags_incremental(self, output_file: str) -> None:
        """增量保存标签池到文件"""
        try:
            # 保存标签列表（按字母顺序）
            with open(output_file, 'w', encoding='utf-8') as f:
                json.dump(sorted(list(self.tag_pool)), f, ensure_ascii=False, indent=2)
            
            # 保存标签统计（按热度排序）
            stats_file = output_file.replace('.json', '_stats.json')
            with open(stats_file, 'w', encoding='utf-8') as f:
                stats_data = {
                    "total_tags": len(self.tag_pool),
                    "total_occurrences": sum(self.tag_counter.values()),
                    "tag_counts": dict(self.tag_counter.most_common()),
                    "top_tags": dict(self.tag_counter.most_common(10))
                }
                json.dump(stats_data, f, ensure_ascii=False, indent=2)
            
        except Exception as e:
            logger.error(f"增量保存标签池失败: {e}")
    
    def save_tags(self, output_file: str) -> None:
        """保存标签池到文件"""
        try:
            # 保存标签列表（按字母顺序）
            with open(output_file, 'w', encoding='utf-8') as f:
                json.dump(sorted(list(self.tag_pool)), f, ensure_ascii=False, indent=2)
            print(f"标签池已保存到: {output_file}")
            
            # 保存标签统计（按热度排序）
            stats_file = output_file.replace('.json', '_stats.json')
            with open(stats_file, 'w', encoding='utf-8') as f:
                stats_data = {
                    "total_tags": len(self.tag_pool),
                    "total_occurrences": sum(self.tag_counter.values()),
                    "tag_counts": dict(self.tag_counter.most_common()),
                    "top_tags": dict(self.tag_counter.most_common(10))
                }
                json.dump(stats_data, f, ensure_ascii=False, indent=2)
            print(f"标签统计已保存到: {stats_file}")
            
        except Exception as e:
            print(f"保存标签池失败: {e}")
    
    def get_statistics(self) -> Dict[str, Any]:
        """获取处理统计信息"""
        return {
            "总标签数": len(self.tag_pool),
            "总出现次数": sum(self.tag_counter.values()),
            "已处理文件数": len(self.processed_files),
            "标签列表": sorted(list(self.tag_pool)),
            "最热标签": dict(self.tag_counter.most_common(10)),
            "标签计数": dict(self.tag_counter.most_common())
        }


def find_article_files(data_dir: str) -> List[str]:
    """查找data目录下的所有文章文件"""
    article_files = []
    data_path = Path(data_dir)
    
    if not data_path.exists():
        print(f"数据目录不存在: {data_dir}")
        return article_files
    
    # 支持的文件扩展名
    supported_extensions = {'.txt', '.md', '.json'}
    
    for file_path in data_path.rglob('*'):
        if file_path.is_file() and file_path.suffix.lower() in supported_extensions:
            article_files.append(str(file_path))
    
    return sorted(article_files)


def main():
    """主函数"""
    parser = argparse.ArgumentParser(description="文章标签处理工具")
    parser.add_argument(
        "--workers", "-w",
        type=int,
        default=4,
        help="并行处理的工作线程数 (默认: 4)"
    )
    parser.add_argument(
        "--content-field", "-f",
        type=str,
        default="content",
        help="指定JSON文件中要读取的内容字段名 (默认: content)"
    )
    parser.add_argument(
        "--incremental-save",
        action="store_true",
        help="启用增量保存，每处理一篇文章就保存一次结果"
    )
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="显示详细日志"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="只显示将要处理的文件，不实际处理"
    )
    
    args = parser.parse_args()
    
    # 设置日志级别
    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)
    
    # 固定路径
    data_dir = "post-tags/data"
    output_file = "tags.json"
    
    logger.info("="*60)
    logger.info("文章标签处理工具启动")
    logger.info(f"工作线程数: {args.workers}")
    logger.info(f"数据目录: {data_dir}")
    logger.info(f"输出文件: {output_file}")
    logger.info(f"内容字段: {args.content_field}")
    logger.info("="*60)
    
    # 验证配置
    logger.info("验证配置...")
    if not settings.validate():
        logger.error("配置验证失败，请检查.env文件")
        print("配置验证失败，请检查.env文件")
        return 1
    logger.info("配置验证通过")
    
    # 查找文章文件
    logger.info(f"在目录 {data_dir} 中查找文章文件...")
    article_files = find_article_files(data_dir)
    
    if not article_files:
        logger.error(f"在 {data_dir} 目录下未找到任何文章文件")
        print(f"在 {data_dir} 目录下未找到任何文章文件")
        return 1
    
    logger.info(f"找到 {len(article_files)} 个文章文件")
    print(f"找到 {len(article_files)} 个文章文件")
    
    if args.dry_run:
        print("将要处理的文件:")
        for file_path in article_files:
            print(f"  - {file_path}")
        logger.info("预览模式完成")
        return 0
    
    
    # 创建处理器
    logger.info("创建标签处理器...")
    try:
        processor = TagProcessor()
        logger.info("标签处理器创建成功")
        
        # 加载之前的状态
        logger.info("尝试加载之前的状态...")
        if processor.load_state(output_file):
            logger.info("成功加载之前的状态")
        else:
            logger.info("未找到之前的状态，将从头开始处理")
    except Exception as e:
        logger.error(f"创建标签处理器失败: {e}")
        print(f"创建标签处理器失败: {e}")
        return 1
    
    # 处理文件
    logger.info(f"开始处理，使用 {args.workers} 个工作线程...")
    print(f"开始处理，使用 {args.workers} 个工作线程...")
    start_time = time.time()
    
    try:
        results = processor.process_files(article_files, args.workers, args.content_field, output_file, args.incremental_save)
        logger.info("文件处理完成")
    except Exception as e:
        logger.error(f"处理文件时发生错误: {e}")
        print(f"处理文件时发生错误: {e}")
        return 1
    
    end_time = time.time()
    processing_time = end_time - start_time
    
    # 显示结果统计
    print("\n" + "="*50)
    print("处理完成!")
    print(f"处理时间: {processing_time:.2f} 秒")
    logger.info(f"处理完成，耗时: {processing_time:.2f} 秒")
    
    # 统计结果
    success_count = sum(1 for r in results if r["status"] == "success")
    failed_count = sum(1 for r in results if r["status"] == "failed")
    skipped_count = sum(1 for r in results if r["status"] == "skipped")
    
    # 统计文章数量
    total_articles = 0
    successful_articles = 0
    failed_articles = 0
    skipped_articles = 0
    
    for result in results:
        if result["status"] == "success":
            if "articles_processed" in result:
                total_articles += result["articles_processed"]
                successful_articles += result["articles_success"]
                failed_articles += result["articles_failed"]
                skipped_articles += result.get("articles_skipped", 0)
            else:
                total_articles += 1
                successful_articles += 1
    
    print(f"成功处理: {success_count} 个文件")
    print(f"处理失败: {failed_count} 个文件")
    print(f"跳过文件: {skipped_count} 个文件")
    print(f"总文章数: {total_articles} 篇")
    print(f"成功文章: {successful_articles} 篇")
    print(f"失败文章: {failed_articles} 篇")
    print(f"跳过文章: {skipped_articles} 篇")
    
    logger.info(f"处理统计 - 文件成功: {success_count}, 文件失败: {failed_count}, 跳过: {skipped_count}")
    logger.info(f"文章统计 - 总数: {total_articles}, 成功: {successful_articles}, 失败: {failed_articles}, 跳过: {skipped_articles}")
    
    # 显示失败文件的详细信息
    if failed_count > 0:
        print("\n失败的文件:")
        for result in results:
            if result["status"] == "failed":
                print(f"  - {result['file']}: {result['reason']}")
                logger.warning(f"文件 {result['file']} 处理失败: {result['reason']}")
    
    # 显示失败文章的详细信息
    if failed_articles > 0:
        print("\n失败的文章:")
        for result in results:
            if result["status"] == "success" and "results" in result:
                for article_result in result["results"]:
                    if article_result["status"] == "failed":
                        print(f"  - {article_result['article']}: {article_result['reason']}")
                        logger.warning(f"文章 {article_result['article']} 处理失败: {article_result['reason']}")
    
    # 显示标签统计
    stats = processor.get_statistics()
    print(f"标签池大小: {stats['总标签数']} 个标签")
    print(f"总出现次数: {stats['总出现次数']} 次")
    logger.info(f"标签池大小: {stats['总标签数']} 个标签")
    logger.info(f"总出现次数: {stats['总出现次数']} 次")
    
    # 显示最热标签
    if stats['最热标签']:
        print(f"\n最热门的标签:")
        for tag, count in list(stats['最热标签'].items())[:5]:
            print(f"  {tag}: {count} 次")
        logger.info(f"最热标签: {stats['最热标签']}")
    
    
    # 保存标签池和状态
    try:
        processor.save_tags(output_file)
        processor.save_state(output_file)
        logger.info(f"标签池已保存到: {output_file}")
        logger.info("处理状态已保存")
    except Exception as e:
        logger.error(f"保存标签池失败: {e}")
        print(f"保存标签池失败: {e}")
        return 1
    
    # 显示部分标签
    if stats['标签列表']:
        print(f"\n部分标签示例: {', '.join(stats['标签列表'][:10])}")
        if len(stats['标签列表']) > 10:
            print(f"... 还有 {len(stats['标签列表']) - 10} 个标签")
        logger.info(f"标签示例: {stats['标签列表'][:10]}")
    
    logger.info("程序执行完成")
    return 0


if __name__ == "__main__":
    exit(main())

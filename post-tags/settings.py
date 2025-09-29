"""
配置模块，从.env文件加载配置
"""
import os
from typing import Optional
from dotenv import load_dotenv

# 加载.env文件
load_dotenv()

class Settings:
    """配置类"""
    
    def __init__(self):
        # OpenAI API配置
        self.openai_api_key: str = os.getenv("OPENAI_API_KEY", "")
        self.openai_base_url: str = os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1")
        self.openai_model: str = os.getenv("OPENAI_MODEL", "gpt-3.5-turbo")
        
        # 处理配置
        self.max_workers: int = int(os.getenv("MAX_WORKERS", "4"))
        self.output_file: str = os.getenv("OUTPUT_FILE", "tags.json")
        self.data_dir: str = os.getenv("DATA_DIR", "post-tags/data")
        
        # 验证必要的配置
        if not self.openai_api_key:
            raise ValueError("OPENAI_API_KEY 环境变量未设置")
    
    def validate(self) -> bool:
        """验证配置是否有效"""
        try:
            if not self.openai_api_key:
                print("错误: OPENAI_API_KEY 未设置")
                return False
            if not os.path.exists(self.data_dir):
                print(f"错误: 数据目录不存在: {self.data_dir}")
                return False
            if not os.path.isdir(self.data_dir):
                print(f"错误: 数据路径不是目录: {self.data_dir}")
                return False
            return True
        except Exception as e:
            print(f"配置验证时发生错误: {e}")
            return False

# 创建全局配置实例
settings = Settings()

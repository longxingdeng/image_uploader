# encoding:utf-8

import requests
import plugins
import os
import json
from bridge.reply import Reply, ReplyType
from bridge.context import ContextType, Context  # 导入 Context 类
from plugins.event import Event, EventAction, EventContext
from channel.chat_message import ChatMessage
from common.log import logger
from bridge.bridge import Bridge  # 调整导入路径
from plugins import Plugin  # 导入 Plugin 类

# 用于暂存用户文本消息的字典
user_text_cache = {}
user_image_cache = {}

@plugins.register(
    name="image_uploader",
    desire_priority=800,  # 确保优先级高于 sum4all
    desc="A plugin for uploading images to sm.ms and combining with text",
    version="0.1.0",
    author="xiaolong",
)
class image_uploader(Plugin):
    def __init__(self):
        super().__init__()
        try:
            curdir = os.path.dirname(__file__)
            config_path = os.path.join(curdir, "config.json")
            if os.path.exists(config_path):
                with open(config_path, "r", encoding="utf-8") as f:
                    self.config = json.load(f)
            else:
                # 使用父类的方法来加载配置
                self.config = super().load_config()

                if not self.config:
                    raise Exception("config.json not found")
            
            # 设置事件处理函数
            self.handlers[Event.ON_HANDLE_CONTEXT] = self.on_handle_context

            # 从配置中提取所需的设置
            self.smms_key = self.config.get("smms_key", "")

            if not self.smms_key:
                raise ValueError("smms_key not found in config")

            logger.info("[image_uploader] inited with smms_key")

        except Exception as e:
            logger.error(f"image_uploader init failed: {e}")

    def on_handle_context(self, e_context: EventContext):
        context = e_context["context"]
        msg: ChatMessage = e_context["context"]["msg"]  # 获取 ChatMessage 对象

        # 获取用户ID
        user_id = msg.from_user_id

        # 处理文字消息
        if context.type == ContextType.TEXT:
            # 缓存用户发送的文字消息
            user_text_cache[user_id] = msg.content
            logger.info(f"缓存用户 {user_id} 的文本消息: {msg.content}")
            # 检查是否有缓存的图片
            if user_id in user_image_cache:
                self.process_combined_message(user_id, context, e_context)

        # 处理图片消息
        elif context.type == ContextType.IMAGE:
            logger.info("on_handle_context: 开始处理图片")
            context.get("msg").prepare()
            image_path = context.content
            logger.info(f"on_handle_context: 获取到图片路径 {image_path}")

            image_url = self.upload_to_smms(image_path)
            if image_url:
                # 缓存用户的图片链接
                user_image_cache[user_id] = image_url
                logger.info(f"缓存用户 {user_id} 的图片链接: {image_url}")
                # 检查是否有缓存的文字消息
                if user_id in user_text_cache:
                    self.process_combined_message(user_id, context, e_context)
            else:
                # 图片上传失败
                reply = Reply()
                reply.type = ReplyType.TEXT
                reply.content = "图片上传失败，请稍后再试"
                e_context["reply"] = reply
                e_context.action = EventAction.BREAK_PASS

    def process_combined_message(self, user_id, context, e_context):
        # 获取缓存的文本和图片
        text_message = user_text_cache.pop(user_id, "")
        image_url = user_image_cache.pop(user_id, "")

        # 整合消息并添加执行工作流的指令
        combined_message = f"执行工作流, {image_url}, {text_message}"
        
        # 缓存整合后的消息
        user_text_cache[user_id] = combined_message
        logger.info(f"缓存用户 {user_id} 的整合消息: {combined_message}")

        # 发送整合后的消息给 ByteDanceCozeBot
        self.send_to_coze_bot(combined_message, context)

        # 返回图片链接给用户
        reply = Reply()
        reply.type = ReplyType.TEXT
        reply.content = f"图片上传成功:\n{image_url}"
        e_context["reply"] = reply
        e_context.action = EventAction.BREAK_PASS

    def upload_to_smms(self, image_path):
        url = 'https://sm.ms/api/v2/upload'
        files = {'smfile': open(image_path, 'rb')}
        headers = {'Authorization': self.smms_key}
        logger.info(f"Uploading image with SMMS Key: {self.smms_key}")
        try:
            response = requests.post(url, files=files, headers=headers)
            response.raise_for_status()  # 检查请求是否成功
            data = response.json()
            if data['success']:
                image_url = data['data']['url']
                logger.info(f"图片上传成功: {image_url}")
                return image_url
            elif data['code'] == 'image_repeated':
                image_url = data['images']
                logger.info(f"图片已存在: {image_url}")
                return image_url
            else:
                logger.error(f"图片上传失败: {data['message']}")
                return None
        except requests.exceptions.RequestException as e:
            logger.error(f"图片上传请求出错: {e}")
            return None

    def send_to_coze_bot(self, message, original_context):
        try:
            # 通过 Bridge 获取 ByteDanceCozeBot 实例并发送消息
            bridge = Bridge()
            coze_bot = bridge.get_bot("chat")  # 获取 ByteDanceCozeBot 实例

            # 从原始 context 复制必要的属性
            context = Context(type=ContextType.TEXT, content=message)
            context["session_id"] = original_context.get("session_id")
            context["msg"] = original_context.get("msg")
            context["user_id"] = original_context.get("user_id")

            reply = coze_bot.reply(message, context)  # 发送消息
            logger.info(f"已将消息发送到 ByteDanceCozeBot: {message}")
            return reply
        except Exception as e:
            logger.error(f"发送消息到 ByteDanceCozeBot 失败: {e}")
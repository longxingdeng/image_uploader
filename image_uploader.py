# encoding:utf-8

import requests
import plugins
import os
import json
from bridge.reply import Reply, ReplyType
from bridge.context import ContextType
from plugins.event import Event, EventAction, EventContext
from channel.chat_message import ChatMessage
from common.log import logger
from bridge.bridge import Bridge  # 调整导入路径

@plugins.register(
    name="image_uploader",
    desire_priority=800,  # 确保优先级高于 sum4all
    desc="A plugin for uploading images to sm.ms and combining with text",
    version="0.1.0",
    author="xiaolong",
)
class image_uploader:
    def __init__(self):
        self.conf = self.load_config()  # 直接调用实例方法
        self.smms_key = self.conf.get("smms_key", "") 
        if not self.smms_key:
            raise ValueError("smms_key not found in config")

        self.handlers = {Event.ON_HANDLE_CONTEXT: self.on_handle_context}  # 初始化 handlers 属性
        logger.info("[image_uploader] inited.")

    def load_config(self):
        # 在这里实现 load_config 方法
        # 返回一个包含配置信息的字典
        return {
            "smms_key": "your_smms_key_here"
        }

    def on_handle_context(self, e_context: EventContext):
        context = e_context["context"]
        msg: ChatMessage = e_context["context"]["msg"]  # 获取 ChatMessage 对象

        # 处理图片消息
        if context.type == ContextType.IMAGE:
            logger.info("on_handle_context: 开始处理图片")
            context.get("msg").prepare()
            image_path = context.content
            logger.info(f"on_handle_context: 获取到图片路径 {image_path}")

            image_url = self.upload_to_smms(image_path)

            if image_url:
                # 返回图片链接给用户
                reply = Reply()
                reply.type = ReplyType.TEXT
                reply.content = f"图片上传成功:\n{image_url}"
                e_context["reply"] = reply

                # 继续处理，将图片链接传递给 ByteDanceCozeBot
                e_context.action = EventAction.CONTINUE

                # 整合图片链接和文本
                combined_message = f"{image_url} , {msg.content}"
                self.send_to_coze_bot(combined_message, context)
            else:
                # 图片上传失败
                reply = Reply()
                reply.type = ReplyType.TEXT
                reply.content = "图片上传失败，请稍后再试"
                e_context["reply"] = reply
                e_context.action = EventAction.BREAK_PASS

            # 删除图片文件
            os.remove(image_path)
            logger.info(f"文件 {image_path} 已删除")

        # 处理文字消息
        elif context.type == ContextType.TEXT:
            # 获取用户发送的文字消息
            text_message = msg.content  # 假设WechatMessage对象有content属性

            # 将文字消息更新到 context 中
            e_context["context"].content = text_message 

    def upload_to_smms(self, image_path):
        url = 'https://sm.ms/api/v2/upload'
        files = {'smfile': open(image_path, 'rb')}
        headers = {'Authorization': self.smms_key}
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

    def send_to_coze_bot(self, message, context):
        try:
            # 通过 Bridge 获取 ByteDanceCozeBot 实例并发送消息
            bridge = Bridge()
            coze_bot = bridge.get_bot("chat")  # 获取 ByteDanceCozeBot 实例
            reply = coze_bot.reply(message, context)  # 发送消息
            logger.info(f"已将消息发送到 ByteDanceCozeBot: {message}")
            return reply
        except Exception as e:
            logger.error(f"发送消息到 ByteDanceCozeBot 失败: {e}")

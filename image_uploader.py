# -*- coding: UTF-8 -*-

import requests
import plugins
from bridge.reply import Reply, ReplyType
from bridge.context import ContextType
from channel.chat_message import ChatMessage
from common.log import logger

@plugins.register(
    name="image_uploader",
    desire_priority=800,
    desc="A plugin for uploading images to sm.ms",
    version="0.1.0",
    author="xiaolong",
)
class ImageUploader(Plugin):
    def __init__(self):
        super().__init__()
        try:
            # 加载配置
            self.config = self.load_config()
            self.smms_key = self.config.get("smms_key", "")
            # 设置事件处理函数
            self.handlers[Event.ON_HANDLE_CONTEXT] = self.on_handle_context
            logger.info("[image_uploader] inited.")
        except Exception as e:
            logger.warn(f"image_uploader init failed: {e}")

    def on_handle_context(self, e_context: EventContext):
        context = e_context["context"]
        if context.type != ContextType.IMAGE:
            return

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
            e_context.action = EventAction.BREAK_PASS
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
            else:
                logger.error(f"图片上传失败: {data['message']}")
                return None
        except requests.exceptions.RequestException as e:
            logger.error(f"图片上传请求出错: {e}")
            return None
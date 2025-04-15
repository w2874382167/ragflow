import os
from openai import OpenAI

class ModelAPI:
    def __init__(self, MODEL_URL=None):
        self.client = OpenAI(
            api_key="sk-a8c6b54b1508476d89f2706d35d1579e",  # 使用环境变量获取API Key
            base_url="https://dashscope.aliyuncs.com/compatible-mode/v1"
        )
        self.model_name = "deepseek-v3"  # 你可以根据需要更换模型名称
        self.messages = []  # 初始化对话上下文

    def add_message(self, role, content):
        """添加消息到对话上下文"""
        self.messages.append({'role': role, 'content': content})

    def chat(self, query, history=None):
        try:
            # 添加用户消息到对话上下文
            self.add_message('user', query)

            # 构建请求
            completion = self.client.chat.completions.create(
                model=self.model_name,
                messages=self.messages
            )

            # 通过content字段获取最终答案
            answer = completion.choices[0].message.content

            # 添加助手消息到对话上下文
            self.add_message('assistant', answer)

            # 如果需要思考过程，可以通过reasoning_content字段获取
            reasoning_content = completion.choices[0].message.reasoning_content if hasattr(completion.choices[0].message, 'reasoning_content') else None

            # 打印思考过程（可选）
            if reasoning_content:
                print("思考过程：")
                print(reasoning_content)

            return answer, history
        except Exception as e:
            print(f"错误信息：{e}")
            print("请参考文档：https://help.aliyun.com/zh/model-studio/developer-reference/error-code")
            return None, history

# 示例使用
if __name__ == "__main__":
    model_api = ModelAPI()

    # 第一轮对话
    query1 = "你好"
    answer1, _ = model_api.chat(query1)
    print("="*20 + "第一轮对话" + "="*20)
    print("用户：", query1)
    print("助手：", answer1)

    # 第二轮对话
    query2 = "你是谁"
    answer2, _ = model_api.chat(query2)
    print("="*20 + "第二轮对话" + "="*20)
    print("用户：", query2)
    print("助手：", answer2)

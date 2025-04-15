import os
from http import HTTPStatus
from dashscope import Application
import json

class LLMEntityLinker:
    def __init__(self, api_key, app_id):
        self.api_key = api_key
        self.app_id = app_id

    def call_llm(self, prompt):
        response = Application.call(
            api_key=self.api_key,
            app_id=self.app_id,
            prompt=prompt
        )

        if response.status_code != HTTPStatus.OK:
            print(f'request_id={response.request_id}')
            print(f'code={response.status_code}')
            print(f'message={response.message}')
            print(f'请参考文档：https://help.aliyun.com/zh/model-studio/developer-reference/error-code')
            return None
        else:
            return response.output.text

    def parse_llm_output(self, llm_output):
        try:
            # 假设LLM的输出是一个JSON字符串
            llm_output_dict = json.loads(llm_output)

            # 提取extracted_entities
            extracted_entities = llm_output_dict.get("extracted_entities", [])

            # 转换为所需的格式
            result = {}
            for entity, entity_type in extracted_entities:
                # 去除可能存在的空格
                entity = entity.strip()
                if isinstance(entity_type, str):
                    entity_type = [entity_type.strip()]
                elif isinstance(entity_type, list):
                    entity_type = [et.strip() for et in entity_type]
                else:
                    entity_type = []

                if entity in result:
                    result[entity].extend(entity_type)
                else:
                    result[entity] = entity_type

            return result
        except Exception as e:
            print(f"解析LLM输出时出错: {e}")
            return {}

    def link_entities(self, query):
        # 构建提示词
        prompt = f"输入：{query}"

        # 调用LLM
        llm_output = self.call_llm(prompt)

        if llm_output:
            # 解析LLM输出
            result = self.parse_llm_output(llm_output)
            return result
        else:
            print("未获取到LLM输出")
            return {}

def main():
    # 示例输入
    user_input = "什么是糖尿病？"

    # 创建LLMEntityLinker实例
    api_key = "sk-a8c6b54b1508476d89f2706d35d1579e"
    app_id = '15b1df2442c64557b0ac6c0a74ca91f5'  # 替换为实际的应用 ID
    entity_linker = LLMEntityLinker(api_key, app_id)

    # 调用link_entities方法
    result = entity_linker.link_entities(user_input)

    # 打印结果
    print(result)

if __name__ == "__main__":
    main()

from kgn_llm.llm_entity_linking import LLMEntityLinker
from kgn_llm.llm_server import *
from kgn_llm.build_medicalgraph import *
import re

api_key = "sk-a8c6b54b1508476d89f2706d35d1579e"
app_id = '15b1df2442c64557b0ac6c0a74ca91f5'  # 替换为实际的应用 ID
entity_linker = LLMEntityLinker(api_key, app_id)

kg = MedicalGraph()
model = ModelAPI(MODEL_URL=None)

class KGRAG():
    def __init__(self):
        self.cn_dict = {
            "name": "名称",
            "desc": "疾病简介",
            "cause": "疾病病因",
            "prevent": "预防措施",
            "cure_department": "治疗科室",
            "cure_lasttime": "治疗周期",
            "cure_way": "治疗方式",
            "cured_prob": "治愈概率",
            "easy_get": "易感人群",
            "belongs_to": "所属科室",
            "common_drug": "常用药品",
            "do_eat": "宜吃",
            "drugs_of": "生产药品",
            "need_check": "诊断检查",
            "no_eat": "忌吃",
            "recommand_drug": "好评药品",
            "recommand_eat": "推荐食谱",
            "has_symptom": "症状",
            "acompany_with": "并发症",
            "Check": "诊断检查项目",
            "Department": "医疗科目",
            "Disease": "疾病",
            "Drug": "药品",
            "Food": "食物",
            "Producer": "在售药品",
            "Symptom": "疾病症状"
        }
        self.entity_rel_dict = {
            "check": ["name", 'need_check'],
            "department": ["name", 'belongs_to'],
            "disease": ["prevent", "cure_way", "name", "cure_lasttime", "cured_prob", "cause", "cure_department", "desc", "easy_get", 'recommand_eat', 'no_eat', 'do_eat', "common_drug", 'drugs_of', 'recommand_drug', 'need_check', 'has_symptom', 'acompany_with', 'belongs_to'],
            "drug": ["name", "common_drug", 'drugs_of', 'recommand_drug'],
            "food": ["name"],
            "producer": ["name"],
            "symptom": ["name", 'has_symptom'],
        }

    def entity_linking(self, query):
        return entity_linker.link_entities(query)

    def link_entity_rel(self, query, entity, entity_type):
        cate = [self.cn_dict.get(i) for i in self.entity_rel_dict.get(entity_type)]
        prompt = "请判定问题：{query}所提及的是{entity}的哪几个信息，请从{cate}中进行选择，并以列表形式返回。".format(query=query, entity=entity, cate=cate)
        answer, history = model.chat(query=prompt, history=[])
        cls_rel = set([i for i in re.split(r"[\[。、, ;'\]]", answer)]).intersection(set(cate))
        print([prompt, answer, cls_rel])
        return cls_rel

    def recall_facts(self, cls_rel, entity_type, entity_name, depth=1):
        entity_dict = {
            "check": "Check",
            "department": "Department",
            "disease": "Disease",
            "drug": "Drug",
            "food": "Food",
            "producer": "Producer",
            "symptom": "Symptom"
        }
        sql = "MATCH p=(m:{entity_type})-[r*..{depth}]-(n) where m.name = '{entity_name}' return p".format(depth=depth, entity_type=entity_dict.get(entity_type), entity_name=entity_name)
        print(sql)
        ress = kg.g.run(sql).data()
        triples = set()
        for res in ress:
            p_data = res["p"]
            nodes = p_data.nodes
            rels = p_data.relationships
            for node in nodes:
                node_name = node["name"]
                for k, v in node.items():
                    if v == node_name:
                        continue
                    if self.cn_dict[k] not in cls_rel:
                        continue
                    triples.add("<" + ','.join([str(node_name), str(self.cn_dict[k]), str(v)]) + ">")
            for rel in rels:
                if rel.start_node["name"] == rel.end_node["name"]:
                    continue
                if rel["name"] not in cls_rel:
                    continue
                triples.add("<" + ','.join([str(rel.start_node["name"]), str(rel["name"]), str(rel.end_node["name"])]) + ">")
        print(len(triples), list(triples)[:3])
        return list(triples)

    def format_prompt(self, query, kg_facts, triple_facts):
        prompt = "这是一个关于医疗领域的问题。给定以下证据，用于回答问题：\n"
        if triple_facts:
            prompt += "知识图谱中的证据：\n" + "\n".join(triple_facts) + "\n"
        if kg_facts:
            prompt += "知识库中的证据：\n" + "\n".join(kg_facts) + "\n"
        prompt += "请先从这些证据中找到能够支撑问题的部分，并基于此回答问题。如果没有找到，那么直接回答没有找到证据，回答不知道，如果找到了，请先回答证据的内容，然后在给出最终答案。\n"
        prompt += "问题是：" + query + "\n请回答，并以Markdown的文档输出："
        return prompt

    def get_triples_from_query(self, query):
        print("step1: linking entity.....")
        entity_dict = self.entity_linking(query)
        depth = 1
        triple_facts = list()

        if entity_dict:
            print("step2：recall kg facts....")
            for entity_name, types in entity_dict.items():
                for entity_type in types:
                    rels = self.link_entity_rel(query, entity_name, entity_type)
                    entity_triples = self.recall_facts(rels, entity_type, entity_name, depth)
                    triple_facts += entity_triples

        # 将三元组格式化为JSON格式
        triples_json = []
        for triple in triple_facts:
            parts = triple.strip('<>').split(',')
            if len(parts) == 3:
                subject, predicate, obj = parts
                triples_json.append({
                    "subject": subject.strip(),
                    "predicate": predicate.strip(),
                    "object": obj.strip()
                })
        return triples_json

def generate_prompt(query, triples):
    prompt = f"问题: {query}\n"
    prompt += "以下是与问题相关的三元组列表：\n"
    for triple in triples:
        prompt += f"- {triple}\n"
    prompt += "请根据问题和三元组列表，选择与问题最相关的三元组，并生成这些三元组的详细介绍。请用简洁的语言回答。如果没有相关三元组，请回答没有找到相关三元组。"
    return prompt

def generate_response(prompt):
    response, _ = model.chat(query=prompt)
    return response.strip()

def generate_answer_from_query(query):
    chatbot = KGRAG()
    triples = chatbot.get_triples_from_query(query)

    # 将三元组转换为字符串格式
    triples_str = [
        f"{{'subject': '{triple['subject']}', 'predicate': '{triple['predicate']}', 'object': '{triple['object']}'}}"
        for triple in triples]

    # 生成提示词
    prompt = generate_prompt(query, triples_str)

    # 生成回答
    response = generate_response(prompt)
    return response

if __name__ == "__main__":
    query = "我感到有些头疼，给我提供一些解决措施。"
    response = generate_answer_from_query(query)
    print(response)

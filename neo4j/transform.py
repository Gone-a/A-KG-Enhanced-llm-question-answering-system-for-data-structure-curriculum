import csv
import json

def csv_to_json(csv_file_path, json_file_path):
    with open(csv_file_path,'r',encoding='utf-8') as csvfile, open(json_file_path,'w',encoding='utf-8') as jsonfile:
        reader=csv.DictReader(csvfile)
        data={}
        relation_dict={
            "rely":"依赖",
            "b-rely":"被依赖",
            "belg":"包含",
            "b-belg":"被包含",
            "syno":"同义",
            "relative":"相对",
            "attr":"拥有",
            "b-attr":"属性",
            "none":"无"
        }



        for row in reader:
            links={
                'source':row['head'],
                'target':row['tail'],
                'relation':relation_dict.get(row['relation'],row['relation'])
            }
        
            nodes=[{
                'id':row['head'],
                'name':row['head']
            },
            {
                'id':row['tail'],
                'name':row['tail']
            }]
            #查询data中是否已经存在nodes,links,只需要唯一的节点和关系
            if nodes[0] not in data.get('nodes',[]):
                data.setdefault('nodes',[]).append(nodes[0])
            if nodes[1] not in data.get('nodes',[]):
                data.setdefault('nodes',[]).append(nodes[1])
            if links not in data.get('links',[]):
                data.setdefault('links',[]).append(links)
        json.dump(data,jsonfile,ensure_ascii=False,indent=2)

if __name__=='__main__':
    csv_file_path='neo4j/data/predictions.csv'
    json_file_path='neo4j/data/predictions.json'
    csv_to_json(csv_file_path,json_file_path)

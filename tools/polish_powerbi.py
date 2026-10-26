import json
from pathlib import Path
root=Path(__file__).resolve().parents[1]/"dashboard/Taxi.Report/definition"
def expr(v):
    return {"expr":{"Literal":{"Value":str(v).lower() if isinstance(v,bool) else str(v)+"D" if isinstance(v,(int,float)) else "'"+v+"'"}}}
for p in root.glob("pages/*/visuals/*/visual.json"):
    d=json.loads(p.read_text(encoding="utf-8-sig"))
    if p.parent.name in ["heading", "note"]: continue
    v=d["visual"]
    title=v.setdefault("visualContainerObjects",{}).setdefault("title",[{"properties":{}}])[0]["properties"]
    title["fontColor"]={"solid":{"color":expr("#183044")}}
    title["bold"]=expr(True)
    title["fontSize"]=expr(12)
    objects=v.setdefault("objects",{})
    if v["visualType"]=="card":
        query=v["query"]["queryState"]["Values"]["projections"][0]["nativeQueryRef"]
        precision=0 if query in ["Eligible pickups","Daily average"] else 2
        objects["labels"]=[{"properties":{"labelDisplayUnits":expr(1),"labelPrecision":expr(precision),"fontSize":expr(32)}}]
        objects["categoryLabels"]=[{"properties":{"show":expr(False)}}]
    if p.parent.name=="ranking":
        projection=v["query"]["queryState"]["Y"]["projections"][0]
        v["query"]["sortDefinition"]={"sort":[{"field":projection["field"],"direction":"Descending"}]}
    if v["visualType"]=="slicer":
        objects["data"]=[{"properties":{"mode":expr("Dropdown")}}]
    name=p.parent.name
    ypos={"daily":285,"ranking":285,"heatmap":580,"curves":275,"zoneerrors":570,"peakerrors":570}
    d["position"]["y"]=55 if name.startswith("filter") else 160 if name.startswith("kpi") else ypos[name]
    p.write_text(json.dumps(d,indent=2),encoding="utf-8")
for page in ["operations","forecast"]:
    p=root/f"pages/{page}/page.json"
    d=json.loads(p.read_text(encoding="utf-8-sig"))
    d["height"]=860
    p.write_text(json.dumps(d,indent=2),encoding="utf-8")
    for name,text,y,font in [
        ("heading","NYC YELLOW TAXI  |  "+("OPERATIONS - 2024 Q1" if page=="operations" else "HISTORICAL ONE-HOUR REPLAY - MARCH"),0,18),
        ("note","Recorded pickups, not unmet demand.  |  See quality_summary for excluded rows.  |  Prior-hour availability is assumed; this is not a live feed.",825,11)]:
        path=root/f"pages/{page}/visuals/{name}/visual.json"
        path.parent.mkdir(parents=True,exist_ok=True)
        path.write_text(json.dumps({"$schema":"https://developer.microsoft.com/json-schemas/fabric/item/report/definition/visualContainer/2.1.0/schema.json",
            "name":name,"position":{"x":20,"y":y,"z":100,"width":1240,"height":44,"tabOrder":100},
            "visual":{"visualType":"textbox","objects":{"general":[{"properties":{"paragraphs":[{"textRuns":[{"value":text,
            "textStyle":{"fontFamily":"Segoe UI","fontSize":str(font)+"pt","color":"#183044","fontWeight":"bold" if name=="heading" else "normal"}}]}]}}]}}},indent=2),encoding="utf-8")
print("Report display definitions updated")


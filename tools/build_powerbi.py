"""Generate a local PBIP project from one immutable release."""
import json
from pathlib import Path
import pandas as pd

ROOT=Path(__file__).resolve().parents[1]
release=Path(json.loads((ROOT/"current_release.json").read_text())["path"])
metrics=json.loads((release/"metrics.json").read_text())
out=ROOT/"dashboard"
report=out/"Taxi.Report"
model=out/"Taxi.SemanticModel"
schema="https://developer.microsoft.com/json-schemas/fabric/item/report/definition"

def save(path,data):
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(data,indent=2,ensure_ascii=False),encoding="utf-8")

save(out/"Taxi.pbip",{"version":"1.0","artifacts":[{"report":{"path":"Taxi.Report"}}],"settings":{"enableAutoRecovery":True}})
save(report/"definition.pbir",{"version":"4.0","datasetReference":{"byPath":{"path":"../Taxi.SemanticModel"}}})
save(model/"definition.pbism",{"version":"4.0","settings":{}})
save(report/"definition/version.json",{"$schema":schema+"/versionMetadata/1.0.0/schema.json","version":"2.0.0"})
save(report/"definition/report.json",{"$schema":schema+"/report/3.0.0/schema.json","themeCollection":{},"settings":{"useEnhancedTooltips":True}})
save(report/"definition/pages/pages.json",{"$schema":schema+"/pagesMetadata/1.0.0/schema.json","pageOrder":["operations","forecast"],"activePageName":"operations"})

tables=[]
for name in ["dim_zone","dim_hour","fact_zone_hourly","forecast_comparison","quality_summary"]:
    frame=pd.read_csv(release/f"{name}.csv",nrows=50)
    cols=[]
    conversions=[]
    for col in frame.columns:
        dtype=frame[col].dtype
        if pd.api.types.is_bool_dtype(dtype): typ,mtype="boolean","type logical"
        elif pd.api.types.is_integer_dtype(dtype): typ,mtype="int64","Int64.Type"
        elif pd.api.types.is_float_dtype(dtype): typ,mtype="double","type number"
        else: typ,mtype="string","type text"
        cols.append({"name":col,"dataType":typ,"sourceColumn":col,"summarizeBy":"none"})
        conversions.append('{"'+col+'", '+mtype+'}')
    path=str(release/f"{name}.csv").replace('"','""')
    expression=[
        "let",
        f'    Source = Csv.Document(File.Contents("{path}"), [Delimiter=",", Encoding=65001, QuoteStyle=QuoteStyle.Csv]),',
        '    Headers = Table.PromoteHeaders(Source, [PromoteAllScalars=true]),',
        '    Typed = Table.TransformColumnTypes(Headers, {'+", ".join(conversions)+'}, "en-US")',
        "in Typed"]
    tables.append({"name":name,"columns":cols,"partitions":[{"name":name,"mode":"import","source":{"type":"m","expression":expression}}]})
ops=next(t for t in tables if t["name"]=="fact_zone_hourly")
forecast=next(t for t in tables if t["name"]=="forecast_comparison")
zones=next(t for t in tables if t["name"]=="dim_zone")
zone_list=", ".join(str(r["zone_id"]) for r in metrics["selected_zones"])
zones["columns"].append({"type":"calculated","name":"model_zone","dataType":"boolean","expression":f"'dim_zone'[zone_id] IN {{ {zone_list} }}","summarizeBy":"none"})
ops["measures"]=[
    {"name":"Eligible pickups","expression":"SUM('fact_zone_hourly'[trip_count])","formatString":"#,0"},
    {"name":"Daily average","expression":"DIVIDE([Eligible pickups], DISTINCTCOUNT('dim_hour'[local_date]))","formatString":"#,0"},
    {"name":"Top 10 coverage","expression":"DIVIDE(CALCULATE([Eligible pickups], KEEPFILTERS('dim_zone'[model_zone] = TRUE())), [Eligible pickups])","formatString":"0.0%"}]
measures={
"Actual pickups":"SUM('forecast_comparison'[actual])",
"Baseline pickups":"SUM('forecast_comparison'[baseline_pred])",
"Model pickups":"SUM('forecast_comparison'[candidate_pred])",
"Baseline MAE":"AVERAGE('forecast_comparison'[baseline_abs_error])",
"Model MAE":"AVERAGE('forecast_comparison'[candidate_abs_error])",
"Baseline WAPE":"DIVIDE(SUM('forecast_comparison'[baseline_abs_error]), SUM('forecast_comparison'[actual]))",
"Model WAPE":"DIVIDE(SUM('forecast_comparison'[candidate_abs_error]), SUM('forecast_comparison'[actual]))",
"MAE improvement":"IF([Baseline MAE] = 0, BLANK(), 1 - DIVIDE([Model MAE], [Baseline MAE]))",
"Forecast coverage":"""VAR Hours = CALCULATE(COUNTROWS('dim_hour'), KEEPFILTERS('dim_hour'[source_month] = "2024-03"))
VAR Zones = CALCULATE(COUNTROWS('dim_zone'), KEEPFILTERS('dim_zone'[model_zone] = TRUE()))
RETURN DIVIDE(COUNTROWS('forecast_comparison'), Hours * Zones)"""
}
forecast["measures"]=[{"name":n,"expression":e,"formatString":"0.0%" if any(t in n for t in ["WAPE","improvement","coverage"]) else "#,0.00"} for n,e in measures.items()]
relationships=[]
for fact in ["fact_zone_hourly","forecast_comparison"]:
    for dim,key in [("dim_zone","zone_id"),("dim_hour","hour_key")]:
        relationships.append({"name":f"{fact}_{dim}","fromTable":fact,"fromColumn":key,"toTable":dim,
            "toColumn":key,"fromCardinality":"many","toCardinality":"one","crossFilteringBehavior":"oneDirection","isActive":True})
save(model/"model.bim",{"name":"NYCTaxi","compatibilityLevel":1601,"model":{
    "culture":"en-US","sourceQueryCulture":"en-US","defaultPowerBIDataSourceVersion":"powerBI_V3",
    "tables":tables,"relationships":relationships,"annotations":[{"name":"PBI_QueryOrder","value":json.dumps([t["name"] for t in tables])}]}})
(out/"measures.dax").write_text("\n\n".join(n+" = "+e for n,e in measures.items()),encoding="utf-8")

def expr(value):
    if isinstance(value,bool): v=str(value).lower()
    elif isinstance(value,(int,float)): v=str(value)+"D"
    else: v="'"+str(value).replace("'","''")+"'"
    return {"expr":{"Literal":{"Value":v}}}

def field(table,name,measure=False):
    return {"field":{("Measure" if measure else "Column"):{"Expression":{"SourceRef":{"Entity":table}},"Property":name}},
            "queryRef":f"{table}.{name}","nativeQueryRef":name}

def visual(page,name,kind,title,x,y,w,h,roles):
    save(report/f"definition/pages/{page}/visuals/{name}/visual.json",{
        "$schema":schema+"/visualContainer/2.1.0/schema.json","name":name,
        "position":{"x":x,"y":y,"z":0,"height":h,"width":w,"tabOrder":0},
        "visual":{"visualType":kind,"query":{"queryState":{r:{"projections":p} for r,p in roles.items()}},
                  "visualContainerObjects":{"title":[{"properties":{"show":expr(True),"text":expr(title),"fontSize":expr(13)}}]},
                  "drillFilterOtherVisuals":True}})

for page,title in [("operations","01 | NYC Taxi Operations — 2024 Q1"),("forecast","02 | Historical One-hour Replay — March")]:
    save(report/f"definition/pages/{page}/page.json",{"$schema":schema+"/page/2.0.0/schema.json",
         "name":page,"displayName":title,"displayOption":"FitToPage","width":1280,"height":800})
    for i,(table,col,label) in enumerate([("dim_hour","local_date","New York date"),("dim_zone","borough","Borough"),("dim_zone","zone_name","Zone")]):
        visual(page,f"filter{i}","slicer",label,20+i*420,15,400,90,{"Values":[field(table,col)]})

for i,m in enumerate(["Eligible pickups","Daily average","Top 10 coverage"]):
    visual("operations",f"kpi{i}","card",m,20+i*420,120,400,110,{"Values":[field("fact_zone_hourly",m,True)]})
visual("operations","daily","lineChart","Daily recorded eligible pickups",20,245,800,280,{
    "Category":[field("dim_hour","local_date")],"Y":[field("fact_zone_hourly","Eligible pickups",True)]})
visual("operations","ranking","clusteredBarChart","Zone ranking — select a borough or zone",840,245,420,530,{
    "Category":[field("dim_zone","zone_name")],"Y":[field("fact_zone_hourly","Eligible pickups",True)]})
visual("operations","heatmap","pivotTable","Weekday × local hour (0 = Monday)",20,540,800,235,{
    "Rows":[field("dim_hour","weekday")],"Columns":[field("dim_hour","local_hour")],
    "Values":[field("fact_zone_hourly","Eligible pickups",True)]})
for i,m in enumerate(["Baseline MAE","Model MAE","Model WAPE","Forecast coverage"]):
    visual("forecast",f"kpi{i}","card",m,20+i*315,120,295,100,{"Values":[field("forecast_comparison",m,True)]})
visual("forecast","curves","lineChart","Hourly actual / weekly baseline / model — UTC axis",20,235,1240,280,{
    "Category":[field("dim_hour","hour_start_utc")],
    "Y":[field("forecast_comparison",m,True) for m in ["Actual pickups","Baseline pickups","Model pickups"]]})
visual("forecast","zoneerrors","clusteredBarChart","MAE by zone",20,530,800,245,{
    "Category":[field("dim_zone","zone_name")],"Y":[field("forecast_comparison",m,True) for m in ["Baseline MAE","Model MAE"]]})
visual("forecast","peakerrors","clusteredColumnChart","Peak vs non-peak MAE (Jan–Feb threshold)",840,530,420,245,{
    "Category":[field("forecast_comparison","peak")],"Y":[field("forecast_comparison",m,True) for m in ["Baseline MAE","Model MAE"]]})
save(out/"binding.json",{"release_id":release.name,"release_path":str(release),"model_id":metrics["model_id"],"desktop_validated":False})
print(out/"Taxi.pbip")

"""Full-volume rerun evidence. Keeps the published release pointer unchanged."""
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import time,uuid
from taxi_project.common import ROOT,read_json,json_write,writer_lock,config,digest
from taxi_project.spark_session import start,read_delta
from taxi_project.lakehouse import build
from pyspark.sql import functions as F

def main():
    with writer_lock():
        pointer=ROOT/"current_release.json"
        original=read_json(pointer)
        checksum=digest(pointer)
        old=read_json(ROOT/"runs"/original["release_id"]/"build.json")
        directory=ROOT/"runs"/("acceptance-"+uuid.uuid4().hex[:8])
        directory.mkdir()
        spark=start(config())
        started=time.perf_counter()
        try:
            new=build(spark,read_json(ROOT/"data/source_manifest.json"),config(),"full",directory)
            checks={}
            for name in ["gold_hourly","gold_daily"]:
                before=read_delta(spark,Path(old["lake"])/name,old["versions"][name])
                after=read_delta(spark,Path(new["lake"])/name,new["versions"][name])
                count=after.count()
                assert before.count()==count
                assert before.exceptAll(after).limit(1).count()==0
                assert after.exceptAll(before).limit(1).count()==0
                checks[name]={"row_count":count,"exact_multiset_equal":True,
                              "before_version":old["versions"][name],"after_version":new["versions"][name]}
            assert old["quality"]==new["quality"]
            assert digest(pointer)==checksum
            result={"status":"SUCCESS","elapsed_seconds":time.perf_counter()-started,
                    "published_release_unchanged":original["release_id"],"quality_identical":True,"tables":checks}
            json_write(directory/"rerun_evidence.json",result)
            json_write(ROOT/"reports/full-rerun.json",result)
            print(result,flush=True)
        finally:
            spark.stop()
if __name__=="__main__":
    main()

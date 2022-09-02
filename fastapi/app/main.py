# uvicorn main:app --reload
# uvicorn app:app --reload --host localhost --host 0.0.0.0 --port 9000

import subprocess
import yaml
from fastapi import FastAPI, HTTPException, UploadFile
from fastapi.responses import FileResponse
import os
import shutil
from pathlib import Path

ROOT_DIR = Path(
    os.environ.get(
        'SIMPLEVIS_DATA',
        Path(__file__).parent.resolve()
    )
)
YOLO_DIR = Path(
    os.environ.get(
        'YOLO_DIR',
        Path().resolve().joinpath('yolov5')
    )
)

UPLOAD_DIR = ROOT_DIR.joinpath("uploaded-files")
DETECT_DIR = ROOT_DIR.joinpath("detected-files")
os.makedirs(UPLOAD_DIR, exist_ok=True)
os.makedirs(DETECT_DIR, exist_ok=True)

PRE_TRAINED = "yolov5s.pt"
CST_TRAINED = "coco_uavs.pt"
PRE_CLASSES = "coco128.yaml"
CST_CLASSES = "uavs2.yaml"
OBJECT_CLASSES = {}
SAFE_2_PROCESS = [".JPG", ".JPEG", ".PNG", ".M4V", ".MOV", ".MP4"]
VIDEO_EXTS = [".m4v", ".mov", ".mp4"]


# Load the classes
with open(YOLO_DIR.joinpath("data").joinpath(CST_CLASSES), 'r') as stream:
    try:
        parsed_yaml = yaml.safe_load(stream)
        OBJECT_CLASSES = parsed_yaml['names']
    except yaml.YAMLError as exc:
        print(exc)

app = FastAPI()


@app.get("/")
def index():
    return {"status": "Everything`s Groovy"}


@app.get("/uploads/get")
def getUploadList():
    return {"images": [f.stem for f in UPLOAD_DIR.iterdir()]}


@app.get("/uploads/get/image/{fname}")
async def main(fname):
    return FileResponse(DETECT_DIR.joinpath("exp").joinpath(fname))


@app.get("/uploads/get/labels/{fname}")
def getLabels(fname):
    labels = get_labels(fname)
    return {"labels": labels}


@app.get("/cleanall")
def cleanall():
    try:
        for f in UPLOAD_DIR.iterdir():
            os.remove(f)
        exp_dir = DETECT_DIR.joinpath("exp")
        for detection in exp_dir.iter_dir():
            shutil.rmtree(detection)
        return {"message": "All directories cleaned."}
    except Exception as err:
        raise HTTPException(
            status_code=500,
            detail=f"An error has occurred: {str(err)}"
        )


@app.post("/detect/{model}")
def detect(file: UploadFile, model):
    if model == "pre-trained":
        runmodel = PRE_TRAINED
    elif model == "custom":
        runmodel = CST_TRAINED
    if isSafe(file.filename):
        # os.chdir("yolov5")
        my_ext = os.path.splitext(file.filename)
        try:
            contents = file.file.read()
            with open(UPLOAD_DIR + "/" + file.filename, 'wb') as f:
                f.write(contents)
        except Exception as err:
            return {"error": err}
        finally:
            file.file.close()
        runArgs = [
            'python3',
            'detect.py',
            '--weights',
            runmodel,
            '--project',
            DETECT_DIR,
            '--exist-ok'
        ]
        print(my_ext)
        if not my_ext[1] in VIDEO_EXTS:
            runArgs.append("--save-txt")
        runArgs.append('--source')
        # print("runArgs: " + str(runArgs))
        runArgs.append(UPLOAD_DIR + "/" + file.filename)
        _ = subprocess.run(runArgs, stdout=subprocess.PIPE)
        if not my_ext[1] in VIDEO_EXTS:
            labels = get_labels(file.filename)
            # msg = {"message": labels}
            return {
                "filename": file.filename,
                "contentType": file.content_type,
                "detectedObj": labels,
                "save_path": UPLOAD_DIR + "/" + file.filename,
                "data": {}
            }
        else:
            try:
                print("something")
                _ = subprocess.run([
                    'mv',
                    DETECT_DIR + '/exp/' + my_ext[0] + '.mp4',
                    DETECT_DIR + '/exp/temp.mp4'
                ], stdout=subprocess.PIPE)
                _ = subprocess.run([
                    'ffmpeg',
                    '-i',
                    DETECT_DIR + '/exp/temp.mp4',
                    '-c:v',
                    'libx264',
                    '-preset',
                    'slow',
                    '-crf',
                    '20',
                    '-c:a',
                    'aac',
                    '-b:a',
                    '160k',
                    '-vf',
                    'format=yuv420p',
                    '-movflags',
                    '+faststart',
                    DETECT_DIR + '/exp/' + my_ext[0] + '.mp4'
                ], stdout=subprocess.PIPE)
                _ = subprocess.run(
                    ['rm', DETECT_DIR + '/exp/temp.mp4'],
                    stdout=subprocess.PIPE
                )
            except Exception as err:
                print(err)
            return {
                "filename": file.filename,
                "contentType": file.content_type,
                "save_path": UPLOAD_DIR + "/" + file.filename,
                "data": {}
            }
    return {
        "message": (
            "Cannot process that file type.\n"
            "Supported types: " + str(SAFE_2_PROCESS)
        )
    }


def countX(lst, x):
    count = 0
    for ele in lst:
        if (ele == x):
            count = count + 1
    return count


def get_labels(filename):
    label_file = os.path.splitext(DETECT_DIR + "/exp/labels/" + filename)[0] + ".txt"  # noqa: E501
    det_list = []
    obs = []
    try:
        with open(label_file) as file:
            lines = file.readlines()
            lines = [line.rstrip() for line in lines]
            for line in lines:
                thisline = line.split()
                det_list.append(int(thisline[0]))
                # print(OBJECT_CLASSES[int(thisline[0])])
                # print (thisline[0])
        det_list.sort()
        obj_list = []
        for c in OBJECT_CLASSES:

            cname = OBJECT_CLASSES[c]
            count = countX(det_list, c)
            if count > 0:
                obj = {"object": cname, "count": count}
                obj_list.append(obj)
        obs = obj_list
    except Exception:
        obs = ["no objects detected"]
    return obs


def isSafe(filename):
    safe = False
    myext = os.path.splitext(filename)
    if myext[1].upper() in SAFE_2_PROCESS:
        safe = True
    return safe

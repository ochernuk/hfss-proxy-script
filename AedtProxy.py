#
# Copyright ANSYS, Inc. Unauthorized use, distribution, or duplication is prohibited.
#

import argparse
import numpy as np
import os
import pprint
import sys
import time

# Include paths necessary to find SCP library
if sys.platform.startswith("win"):
    for p in os.environ["PYTHON_DLL_PATH"].split(os.pathsep):
        os.add_dll_directory(p)

# Import SCP library
from pyExt import SystemCouplingParticipant as sysc

# Inclue paths necessary to find AEDT
aedtPath = os.environ["ANSYSEM_ROOT242"]
sys.path.append(aedtPath)
sys.path.append(os.path.join(aedtPath, "PythonFiles", "DesktopPlugin"))

# Import modules necessary to control AEDT
import ScriptEnv
import AedtRunner

# Parse through arguments
parser = argparse.ArgumentParser()
parser.add_argument("--schost", type=str, default="")
parser.add_argument("--scport", type=int, default=0)
parser.add_argument("--scname", type=str, default="")
parser.add_argument("--screstart", type=str, default="")
parser.add_argument("--gui", default=False, action="store_true")
parser.add_argument("--printsol", default=False, action="store_true")

""" Parse input arguments. """
args = parser.parse_args()

buildInfo = "Aedt Proxy"

nodeIds = dict()
nodeCoords = dict()
solutionData = dict()


def solve(oProject, currTime):
    AedtRunner.run(oProject, nodeCoords, solutionData, currTime)


def init():
    """Start AEDT, read and fill in point coordinates and initial values."""
    ScriptEnv.Initialize("Ansoft.ElectronicsDesktop", NG=not args.gui)

    def fillRegion(regionName):
        fileName = f"{regionName}.pts"
        assert os.path.isfile(fileName)
        ids = list()
        coords = list()
        with open(fileName) as inputFile:
            for index, line in enumerate(inputFile.readlines()):
                xStr, yStr, zStr = line.split(" ")
                x, y, z = float(xStr), float(yStr), float(zStr)
                ids.append(index)
                coords.append([x, y, z])

            nodeIds[regionName] = np.array(ids)
            nodeCoords[regionName] = np.array(coords)
            solutionData[regionName] = dict()
            solutionData[regionName]["Loss Density"] = np.array([0.0] * len(ids))
            solutionData[regionName]["Temperature"] = np.array([300.0] * len(ids))

    fillRegion("Die1")
    fillRegion("Die2")


def openPrj():
    oDesktop.RestoreWindow()
    oDesktop.OpenProject("Tee.aedt")
    oProject = oDesktop.SetActiveProject("Tee")
    return oProject


def shutdown():
    ScriptEnv.Shutdown()


def getPointCloud(regionName):
    return sysc.PointCloud(
        sysc.OutputIntegerData(nodeIds[regionName]),
        sysc.OutputVectorData(nodeCoords[regionName]),
    )


def getOutputScalar(regionName, variableName):
    return sysc.OutputScalarData(solutionData[regionName][variableName])


def getInputScalar(regionName, variableName):
    return sysc.InputScalarData(solutionData[regionName][variableName])


def getRestartPoint():
    return "1"


def getSystemCoupling(participantInfo):
    try:
        sc = sysc.SystemCoupling(participantInfo)
        print("Connected to System Coupling.")
        return sc
    except Exception as e:
        print(f"ERROR: {e}. Shutting down AEDT...")
        print("done. Exiting...")
        sys.exit(1)


partInfo = sysc.ParticipantInfo(args.schost, args.scport, args.scname, buildInfo)

# alternatively, set it to "batch.log" to display printouts from that file
partInfo.transcriptFilename = f"{args.scname}.stdout"
sc = getSystemCoupling(partInfo)

exitCode = 0

try:
    sc.registerPointCloudAccess(getPointCloud)
    sc.registerOutputScalarDataAccess(getOutputScalar)
    sc.registerInputScalarDataAccess(getInputScalar)
    sc.registerRestartPointCreation(getRestartPoint)

    startTime = time.time()
    init()
    oProject = openPrj()
    # perform initial solve to get initial values
    print("Performing initial HFSS solve...")
    solve(oProject, currTime=0.0)
    print(f"Initialized HFSS. Time = {time.time() - startTime} [s]")
    print(solutionData)

    startTime = time.time()
    print("Initializing the coupled analysis...")
    sc.initializeAnalysis()
    print(f"Initialized System Coupling. Time = {time.time() - startTime} [s]")

    while sc.doTimeStep():
        ts = sc.getCurrentTimeStep()
        print(
            f"  Time step. Start time = {ts.startTime} [s], time step size = {ts.timeStepSize} [s]"
        )
        iter = 1
        while sc.doIteration():
            print(f"    Iteration {iter}")
            sc.updateInputs()
            print("      Updated inputs. Solving HFSS...")
            startTime = time.time()
            solve(oProject, currTime=ts.startTime + ts.timeStepSize)
            print(f"      Solved HFSS. Time = {time.time() - startTime} [s]")
            if args.printsol:
                pprint.pprint(solutionData)
            sc.updateOutputs(sysc.Complete)
            print("      Updated outputs.")
            iter += 1

    print(f"Saving AEDT project...")
    oProject.Save()
    print(f"Disconnecting...")
    sc.disconnect()
    print("Shutdown.")
except Exception as e:
    print(f"ERROR: {e}.")
    try:
        sc.fatalError(str(e))
    finally:
        exitCode = 1
finally:
    # make sure to always shut down AEDT
    shutdown()

print("SUCCESS! Exiting...")
sys.exit(exitCode)

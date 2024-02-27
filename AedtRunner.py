import re
import os


def run(oProject, points, solutionData, currTime):

    d1pInit = 2.4
    d2pInit = 3.2
    d1tInit = 4e-8
    d2tInit = 5e-8

    minPermittivity = 1.0
    minTangentLoss = 1e-9

    def fillMatrialProps(regionName, permittivity, tangent, pInit, tInit):

        for point, temperatureValue in zip(
            points[regionName], solutionData[regionName]["Temperature"]
        ):
            x = point[0]
            y = point[1]
            z = point[2]
            perm1 = pInit
            loss1 = tInit
            if temperatureValue >= 300.0 and temperatureValue <= 400.0:
                perm1 = ((minPermittivity - pInit) / (400.0 - 300.0)) * (
                    temperatureValue - 300.0
                ) + pInit
                loss1 = ((minTangentLoss - tInit) / (400.0 - 300.0)) * (
                    temperatureValue - 300.0
                ) + tInit
            elif temperatureValue > 400.0:
                perm1 = minPermittivity
                loss1 = minTangentLoss
            permittivity.append(["NAME:Point", x, y, z, perm1])
            tangent.append(["NAME:Point", x, y, z, loss1])

    def getNewDataSetValues():
        dataSetValues = list()
        dataSetValues.append("NAME:Coordinates")
        dataSetValues.append(["NAME:DimUnits", "meter", "meter", "meter", ""])
        return dataSetValues

    dsDie1Perm = getNewDataSetValues()
    dsDie1Tangent = getNewDataSetValues()
    dsDie2Perm = getNewDataSetValues()
    dsDie2Tangent = getNewDataSetValues()

    fillMatrialProps("Die1", dsDie1Perm, dsDie1Tangent, pInit=d1pInit, tInit=d1tInit)
    fillMatrialProps("Die2", dsDie2Perm, dsDie2Tangent, pInit=d2pInit, tInit=d2tInit)

    def addDataSet(oProject, name, values):
        dataSetToAdd = list()
        dataSetToAdd.append(f"NAME:${name}")
        dataSetToAdd.append(values)
        oProject.AddDataset(dataSetToAdd)

    die1PermDatasetName = "dsDie1Perm"
    die1TangDatasetName = "dsDie1Tangent"
    die2PermDatasetName = "dsDie2Perm"
    die2TangDatasetName = "dsDie2Tangent"

    addDataSet(oProject, die1PermDatasetName, dsDie1Perm)
    addDataSet(oProject, die1TangDatasetName, dsDie1Tangent)
    addDataSet(oProject, die2PermDatasetName, dsDie2Perm)
    addDataSet(oProject, die2TangDatasetName, dsDie2Tangent)

    def editMaterialCommon(oDefinitionManager, name, permittivityString, tangentString):
        oDefinitionManager.EditMaterial(
            f"{name}",
            [
                f"NAME:{name}",
                "CoordinateSystemType:=",
                "Cartesian",
                "BulkOrSurfaceType:=",
                1,
                ["NAME:PhysicsTypes", "set:=", ["Electromagnetic"]],
                [
                    "NAME:ModifierData",
                    [
                        "NAME:SpatialModifierData",
                        "modifier_data:=",
                        "spatial_modifier_data",
                        ["NAME:all_spatial_modifiers"],
                    ],
                ],
                "permittivity:=",
                permittivityString,
                "permeability:=",
                "0.999991",
                "conductivity:=",
                "0.0",
                "dielectric_loss_tangent:=",
                tangentString,
                "thermal_conductivity:=",
                "237.5",
                "mass_density:=",
                "2689",
                "specific_heat:=",
                "951",
                "youngs_modulus:=",
                "69000000000",
                "poissons_ratio:=",
                "0.31",
                "thermal_expansion_coefficient:=",
                "2.33e-05",
            ],
        )

    def editMaterialUseConst(oDefinitionManager, name, permVal, tangVal):
        editMaterialCommon(oDefinitionManager, name, f"{permVal}", f"{tangVal}")

    def editMaterialUseDataset(oDefinitionManager, name, dsPermName, dsTangName):
        editMaterialCommon(
            oDefinitionManager,
            name,
            f"clp(${dsPermName},X,Y,Z)",
            f"clp(${dsTangName},X,Y,Z)",
        )

    oDefinitionManager = oProject.GetDefinitionManager()

    editMaterialUseDataset(
        oDefinitionManager, "die1", die1PermDatasetName, die1TangDatasetName
    )
    editMaterialUseDataset(
        oDefinitionManager, "die2", die2PermDatasetName, die2TangDatasetName
    )

    oDesign = oProject.SetActiveDesign("TeeModel")
    oDesign.Analyze("Setup1")
    oModule = oDesign.GetModule("FieldsReporter")
    oModule.CopyNamedExprToStack("Volume_Loss_Density")

    # fill outputs

    def writeOutputs(oModule, regionName):

        outputFileName = f"{regionName}.fld"

        if os.path.exists(outputFileName):
            os.remove(outputFileName)

        oModule.ExportToFile(
            outputFileName,
            f"{regionName}.pts",
            "Setup1 : LastAdaptive",
            ["Freq:=", "10GHz", "Phase:=", "0deg", "offset:=", "0in"],
            [
                "NAME:ExportOption",
                "IncludePtInOutput:=",
                True,
                "RefCSName:=",
                "Global",
                "PtInSI:=",
                True,
                "FieldInRefCS:=",
                False,
            ],
        )

        lossDensityArray = solutionData[regionName]["Loss Density"]
        with open(outputFileName) as vldFile:
            vldFile.readline()  # skip first line
            for index, line in enumerate(vldFile.readlines()):
                # split by arbutrary number of contiguous white spaces
                lineValues = re.split("\s+", line.strip())
                vldValue = float(lineValues[3])
                lossDensityArray[index] = vldValue

    writeOutputs(oModule, "Die1")
    writeOutputs(oModule, "Die2")

    # delete datasets
    # need to dereference the datasets first
    editMaterialUseConst(oDefinitionManager, "die1", d1pInit, d1tInit)
    editMaterialUseConst(oDefinitionManager, "die2", d2pInit, d2tInit)
    # then, need to save the project
    oProject.Save()
    # now, can delete datasets
    for datasetName in [
        die1PermDatasetName,
        die1TangDatasetName,
        die2PermDatasetName,
        die2TangDatasetName,
    ]:
        oProject.DeleteDataset(f"${datasetName}")

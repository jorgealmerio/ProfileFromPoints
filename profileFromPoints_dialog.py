# -*- coding: utf-8 -*-
"""
/***************************************************************************
 ProfileFromPointsDialog
                                 A QGIS plugin
 Plots profile or cross section of survey points
                             -------------------
        begin                : 2016-07-27
        git sha              : $Format:%H$
        copyright            : (C) 2016 by North Dakota State Water Commission
        email                : mweier@nd.gov
 ***************************************************************************/

/***************************************************************************
 *                                                                         *
 *   This program is free software; you can redistribute it and/or modify  *
 *   it under the terms of the GNU General Public License as published by  *
 *   the Free Software Foundation; either version 2 of the License, or     *
 *   (at your option) any later version.                                   *
 *                                                                         *
 ***************************************************************************/
"""
from __future__ import print_function
from __future__ import absolute_import
from builtins import str
from builtins import zip

import os
import numpy as np
from operator import itemgetter

from shapely.geometry import Point
from shapely.geometry import LineString

from qgis.PyQt import QtGui, uic, QtWidgets
from qgis.PyQt.QtWidgets import QApplication, QMessageBox
from qgis.PyQt.QtCore import QVariant, Qt
import processing

from qgis.core import QgsVectorLayer, QgsFeature, QgsGeometry, QgsProject
#
from matplotlib.backends.backend_qt4agg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.backends.backend_qt4agg import NavigationToolbar2QT as NavigationToolbar
from matplotlib.figure import Figure
from matplotlib.ticker import ScalarFormatter

from . import profilefrompoints_utils as utils

FORM_CLASS, _ = uic.loadUiType(os.path.join(
    os.path.dirname(__file__), 'profileFromPoints_dialog_base.ui'))


class ProfileFromPointsDialog(QtWidgets.QDialog, FORM_CLASS):
    proj=QgsProject.instance()
    def __init__(self, parent=None):
        """Constructor."""
        super(ProfileFromPointsDialog, self).__init__(parent)
        # Set up the user interface from Designer.
        # After setupUI you can access any designer object by doing
        # self.<objectname>, and you can use autoconnect slots - see
        # http://qt-project.org/doc/qt-4.8/designer-using-a-ui-file.html
        # #widgets-and-dialogs-with-auto-connect
        self.setupUi(self)
        
        # add matplotlib figure to dialog
        self.figure = Figure()
        self.axes = self.figure.add_subplot(111)
#        self.figure.subplots_adjust(left=.1, bottom=0.15, right=.78, top=.9, wspace=None)
        self.mplCanvas = FigureCanvas(self.figure)
        
        self.mpltoolbar = NavigationToolbar(self.mplCanvas, self.toolbarWidget)
        lstActions = self.mpltoolbar.actions()
        self.mpltoolbar.removeAction(lstActions[7])
        self.layoutPlot.addWidget(self.mplCanvas)
        self.layoutPlot.addWidget(self.mpltoolbar)
        self.figure.patch.set_visible(False)
        self.layoutPlot.minimumSize() 

        
        
        ##connections      
        self.buttonBox.accepted.connect(self.accept)
        self.buttonBox.rejected.connect(self.reject)
        self.uPointLayer.currentIndexChanged.connect(self.reloadFields)
 
        self.uLineLayer.currentIndexChanged.connect(self.checkSelectedLine)
        self.uCopytoClip.clicked.connect(self.copyClipboard)

        self.manageGui()

    def manageGui(self):
        # print('manageGui')
        self.uPointLayer.clear()
        self.uPointLayer.addItems(utils.getPointLayerNames())
        self.uLineLayer.clear()
        self.uLineLayer.addItems(utils.getLineLayerNames())

    def reloadFields(self):
        # print('reload fields')
        self.uZfield.clear()
        self.uPointID.clear()
        self.uOrderField.clear()

        self.axes.clear()

        point_layer = self.proj.mapLayersByName(self.uPointLayer.currentText())[0] #processing.getObject(str())
        if point_layer.selectedFeatureCount() != 0:
            self.uSelectedPoints.setCheckState(Qt.Checked)
        else:
            self.uSelectedPoints.setCheckState(Qt.Unchecked)
        
        self.uZfield.addItems(utils.getFieldNames(point_layer, [QVariant.Int, QVariant.Double]))
        self.uOrderField.addItems(utils.getFieldNames(point_layer, [QVariant.Int, QVariant.Double]))
        self.uPointID.addItems(utils.getFieldNames(point_layer, [QVariant.Int, QVariant.Double, 10]))# 10 is for string
        
    def checkSelectedLine(self):
        ###print 'check if line layer selected'
        line_layer = self.proj.mapLayersByName(self.uLineLayer.currentText())[0] #processing.getObject(str())
        if line_layer:
            if line_layer.selectedFeatureCount() != 0:
                self.uSelectedLine.setCheckState(Qt.Checked)             
            else:
                self.uSelectedLine.setCheckState(Qt.Unchecked)
                
    def copyClipboard (self):
        if self.values is None:
            return
        else:
            clipboard = QApplication.clipboard()
            if self.uNoHeader.isChecked():
                clipboard.setText('\n'.join('%s\t%s' % x for x in zip(self.values[0],self.values[1])))
            else:
                clipboard.setText('distance\televation\tpointID\n'+'\n'.join('%s\t%s\t%s' % x for x in zip(self.values[0],self.values[1],self.values[2])))
            

    def restoreGui(self):
        self.buttonBox.rejected.connect(self.reject)
        self.btnClose.clicked.disconnect(self.stopProcessing)
        self.btnClose.setText(self.tr("Close"))
        self.btnOk.setEnabled(True)
        self.uprogressBar.setMaximum(100)

    def refreshPlot(self):
        self.axes.clear()

        if self.values is None:
            return

        self.axes.plot(np.array(self.values[0]),np.array(self.values[1]))
        
        ###to draw labels from jorgealmerio 
        if self.uPointIDlabels.isChecked():
            for i,linha in enumerate(np.array(self.values[2])):
                id=self.values[2][i]
                dist=self.values[0][i]
                z=self.values[1][i]
                self.axes.annotate(id,(dist,z))


        self.axes.grid()
        formatter = ScalarFormatter(useOffset=False)
        self.axes.yaxis.set_major_formatter(formatter)

        self.axes.set_ylabel(str(self.tr("Elevation, z field units")))
        self.axes.set_xlabel(str(self.tr('Station, layer units')))

        self.mplCanvas.draw()  


    def buildLine(self, pointSelectFlag):
        # print('buildLine')
        pointLayer = self.proj.mapLayersByName(self.uPointLayer.currentText())[0]#processing.getObject(str())
        orderField = self.uOrderField.currentText()
        sortOrder = self.uOrder.currentText()
        crs = pointLayer.crs().toWkt()

        pointList = []
        if pointSelectFlag:
            pointFeatureList = pointLayer.selectedFeatures()
        else:
            pointFeatureList = pointLayer.getFeatures()        
        for pointFeature in pointFeatureList:
            pointGeom = pointFeature.geometry()
            coords = pointGeom.asPoint()
            sortField = pointFeature[orderField]
            ##store data
            pointList.append([coords, sortField])
        
        if not pointFeatureList:
            QMessageBox.warning(self,'Error',
                                        'Selected point list is empty')
            return 'Error'
        ###sort data by field
        if sortOrder=='Ascending':
            pointList = sorted(pointList, key=itemgetter(1))  
        else:
            pointList = sorted(pointList, key=itemgetter(1), reverse=True)  
        
        ## drop sort field
        pointList = list(zip(*pointList))[0] #list(zip(*pointList)[0])
        
        ###build line
        # create a new memory layer
        newLineLayer = QgsVectorLayer("LineString?crs="+crs, "profileFromPointsLine", "memory")
        pr = newLineLayer.dataProvider()
        feat = QgsFeature()
        geom = QgsGeometry.fromPolylineXY(pointList)
        feat.setGeometry(geom)
        pr.addFeatures( [ feat ] )
        
        newLineLayer.updateExtents()
        QgsProject.instance().addMapLayers([newLineLayer])
        return newLineLayer


    def accept(self):
        # print('run')
        pointLayer = self.proj.mapLayersByName(self.uPointLayer.currentText())[0] #processing.getObject(str())
        # check for selected features
        if self.uSelectedPoints.isChecked():
            pointSelectFlag = True
        else:
            pointSelectFlag = False
        if self.uSelectedLine.isChecked():
            lineSelectFlag = True
        else:
            lineSelectFlag = False
        ## check if need to build line
        if self.utabWidget.currentIndex()==0:
            lineLayer = self.buildLine(pointSelectFlag) 
            if lineLayer=='Error':
                return
        else:
            lineLayer = self.proj.mapLayersByName(self.uLineLayer.currentText())[0] #processing.getObject(str())

        zField = self.uZfield.currentText()
        pointIdField = self.uPointID.currentText()
        try:
            noData = float(self.lineEditNoData.text())
        except:
            QMessageBox.warning(self,'Error',
                                'No data value must be numeric')
            return
        if self.uBuffer.displayText() !='':
            buff=float(self.uBuffer.displayText())
        else:
            buff=None
        
        # trap for coordinate system
        if lineLayer.crs()!=pointLayer.crs():
            QMessageBox.warning(self,'Error',
                                'Point layer coordinate system does not match line coordinate system')
            return
            


        # trap for more than one line feature
        counter = 0
        if lineSelectFlag:
            lineFeatureList = lineLayer.selectedFeatures()
        else:
            lineFeatureList = lineLayer.getFeatures()
        
        for lineFeatures in lineFeatureList:
                counter = counter+1

        if counter!=1:
            QMessageBox.warning(self,'Error',
                                'More than one line feature in line layer')
            return
        
        if lineSelectFlag:
            lineFeat = lineLayer.selectedFeatures()[0]
        else:
            lineFeat = next(lineLayer.getFeatures())
        lineGeom = lineFeat.geometry()
        lineShap = LineString(lineGeom.asPolyline())
        if buff:
            lineBoundary = lineShap.buffer(buff)
        
        
        if pointSelectFlag:
            pointFeatureList = pointLayer.selectedFeatures()
        else:
            pointFeatureList = pointLayer.getFeatures()
        pointList = []
        for pointFeature in pointFeatureList:
            pointGeom = pointFeature.geometry()
            pointShap = Point(pointGeom.asPoint())
            if buff:
                ## check if point is within line buffer
                if pointShap.within(lineBoundary):
                    z = pointFeature[zField]
                    ### get distance along line
                    dist = lineShap.project(pointShap)
                    pointId = pointFeature[pointIdField]
                    ##store data
                    pointList.append([dist, z, pointId])
            else:
                z = pointFeature[zField]
                ### get distance along line
                dist = lineShap.project(pointShap)
                pointId = pointFeature[pointIdField]
                ##store data
                pointList.append([dist, z, pointId])                    
        ###sort data by distance
        pointList = sorted(pointList, key=itemgetter(0))  
        ###seperate data back into individual lists
        zList = []
        distList = []
        pointIdList = []
        for i in pointList:
            ## only keep data that is not flaged as noData
            if i[1]!=noData:
                distList.append(i[0])
                zList.append(i[1])
                pointIdList.append(i[2])
        self.values = [distList, zList, pointIdList]
        self.refreshPlot()
        self.uCopytoClip.setEnabled(True)
    


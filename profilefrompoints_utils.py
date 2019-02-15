# -*- coding: utf-8 -*-

"""
/***************************************************************************
 ProfilefromPointsDialog
                                 A QGIS plugin
 Plots a profile from point survey data using a temporary spatialite database
                             -------------------
        begin                : 2014-10-15
        copyright            : (C) 2014 by Mitchell Weier - North Dakota State Water Commission
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
from builtins import str
from builtins import object

import locale

from qgis.PyQt.QtCore import *
from qgis.PyQt.QtGui import *

from qgis.core import *
from qgis.gui import *

try:
    from pyspatialite import dbapi2 as db
except:
    QgsMessageLog.logMessage('pyspatialite')

class spatialiteManager(object):
    def __init__(self, dbase):
        # get a connection, if a connect cannot be made an exception will be raised here
        self.conn = db.connect(dbase)
        self.cur = self.conn.cursor()

    def createDB(self):
        # initializing Spatial MetaData
        # using v.2.4.0 this will automatically create
        # GEOMETRY_COLUMNS and SPATIAL_REF_SYS
        sql = 'SELECT InitSpatialMetadata()'
        self.query(sql)

    def query(self, sql):
        self.cur.execute(sql)
        self.conn.commit()
        return self.cur
        
    def spatialIndex(self, table, geomCol):
        sql = """SELECT CreateSpatialIndex('{0}', '{1}')""".format(table, geomCol)
        self.cur.execute(sql)
        self.conn.commit()
        
    def removeSpatialIndex(self, table, geomCol):
        sql = """SELECT DisableSpatialIndex('{0}', '{1}')""".format(table, geomCol)
        self.cur.execute(sql)
        self.conn.commit()
        sql = """DROP TABLE idx_{}_{}""".format(table, geomCol)
        self.cur.execute(sql)
        self.conn.commit()       

    def dropTables(self,tables):
        for i in tables:
            sql = '''DROP TABLE IF EXISTS {}'''.format(i)
            self.cur.execute(sql)
            self.conn.commit()        
        self.cur.execute('VACUUM')
        self.conn.commit()
        
    def discardGeom(self, table, geomCol):
        sql = """SELECT DiscardGeometryColumn('{}', '{}')""".format(table, geomCol)
        self.cur.execute(sql)
        self.conn.commit()

    def __del__(self):
        # fix_print_with_import
        print('close db')
        self.conn.close() 



def getPointLayerNames():
    layerMap = QgsProject.instance().mapLayers()
    layerNames = []
    for name, layer in layerMap.items():
        if layer.type() == QgsMapLayer.VectorLayer and layer.wkbType()==QgsWkbTypes.Point:
            layerNames.append(str(layer.name()))
    return sorted(layerNames)#, cmp=locale.strcoll)
    
def getLineLayerNames():
    layerMap = QgsProject.instance().mapLayers()
    layerNames = []
    for name, layer in layerMap.items():
        if layer.type() == QgsMapLayer.VectorLayer and layer.wkbType()==QgsWkbTypes.LineString:
            layerNames.append(str(layer.name()))
    return sorted(layerNames)#, cmp=locale.strcoll)


def getVectorLayerByName(layerName):
    layerMap = QgsProject.instance().mapLayers()
    for name, layer in layerMap.items():
        if layer.type() == QgsMapLayer.VectorLayer and layer.name() == layerName:
            if layer.isValid():
                return layer
            else:
                return None


def getFieldNames(layer, fieldTypes):
    fields = layer.fields()
    fieldNames = []
    for field in fields:
        if field.type() in fieldTypes and not field.name() in fieldNames:
            fieldNames.append(str(field.name()))
    return fieldNames


def getFieldType(layer, fieldName):
    fields = layer.fields()
    for field in fields:
        if field.name() == fieldName:
            return field.typeName()


def getUniqueValuesCount(layer, fieldIndex, useSelection):
    count = 0
    values = []
    if useSelection:
        for f in layer.selectedFeatures():
            if f[fieldIndex] not in values:
                values.append(f[fieldIndex])
                count += 1
    else:
        request = QgsFeatureRequest().setFlags(QgsFeatureRequest.NoGeometry)
        for f in layer.getFeatures(request):
            if f[fieldIndex] not in values:
                values.append(f[fieldIndex])
                count += 1
    return count

def checkMultipart(layer):
    for f in layer.getFeatures():
        if f.geometry().isMultipart():
            return True
    return False
  
def createDB(layer, dbase, srid):
    # setup spatilite manager
    dbmgr = spatialiteManager(dbase)
    # create database
    dbmgr.createDB()
    # for custom CRS,  check if projection doesn't exist in spatialite database
    sql = """SELECT COUNT(*) FROM spatial_ref_sys WHERE srid = {}""".format(srid)
    count = dbmgr.query(sql).fetchall()[0][0]
    if count == 0: # add def. if needed
        sql = """INSERT INTO spatial_ref_sys(srid, auth_name, auth_srid, ref_sys_name, proj4text, srtext) VALUES({0}, '', '', '{3}', '{1}', '{2}')""".format(srid, layer.crs().toProj4(), layer.crs().toWkt(), layer.crs().description())
        dbmgr.query(sql)
        customCRSFlag = True  
    else:
        customCRSFlag = False
    return customCRSFlag
  
def loadVectorsIntoDB(layers, dbase, customCRSFlag, srid):
    #database import options
    options = {}
    options['overwrite'] = True
    options['forceSinglePartGeometryType'] = True
    uri = QgsDataSourceURI()
    uri.setDatabase(dbase)
    for layer in layers:
        uri.setDataSource('',layer.name(),'the_geom')
        ret, errMsg = QgsVectorLayerImport.importLayer(layer, uri.uri(), 'spatialite', layer.crs(), False, False, options)
        
        ## for custom CRS
        if customCRSFlag:
            dbmgr = spatialiteManager(dbase)
            sql = """UPDATE geometry_columns SET srid = {} WHERE f_table_name = '{}'""".format(srid, layer.name().lower())
            dbmgr.query(sql)
            sql = """UPDATE {} SET the_geom = SetSRID(the_geom, {})""".format(layer.name(), srid)
            dbmgr.query(sql)



#def is_number(s):
#    try:
#        float(s)
#        return True
#    except ValueError:
#        return False
        
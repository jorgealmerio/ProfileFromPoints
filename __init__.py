# -*- coding: utf-8 -*-
"""
/***************************************************************************
 ProfileFromPoints
                                 A QGIS plugin
 Plots profile or cross section of survey points
                             -------------------
        begin                : 2016-07-27
        copyright            : (C) 2016 by North Dakota State Water Commission
        email                : mweier@nd.gov
        git sha              : $Format:%H$
 ***************************************************************************/

/***************************************************************************
 *                                                                         *
 *   This program is free software; you can redistribute it and/or modify  *
 *   it under the terms of the GNU General Public License as published by  *
 *   the Free Software Foundation; either version 2 of the License, or     *
 *   (at your option) any later version.                                   *
 *                                                                         *
 ***************************************************************************/
 This script initializes the plugin, making it known to QGIS.
"""


# noinspection PyPep8Naming
def classFactory(iface):  # pylint: disable=invalid-name
    """Load ProfileFromPoints class from file ProfileFromPoints.

    :param iface: A QGIS interface instance.
    :type iface: QgsInterface
    """
    #
    from .profileFromPoints import ProfileFromPoints
    return ProfileFromPoints(iface)

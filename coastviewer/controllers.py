import logging
import datetime
import io

import flask
import flask_cors
import pandas as pd
import numpy as np
import matplotlib.cm
import matplotlib.colors
import matplotlib.pyplot as plt
import geojson

from . import datasets
from . import utils
from . import plots
from . import __version__

logger = logging.getLogger(__name__)

MIMES = {
    'png': 'image/png',
    'svg': 'image/svg+xml',
    'pdf': 'application/pdf',
    'csv': 'text/csv',
    'json': 'application/json',
    'xls': 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
}

def index(api: object) -> str:
    # can't name this index (already taken by conexxion)
    return flask.render_template("main.html", api=api)


def transect(id: int) -> object:
    logger.info(flask.request)
    return {}


@flask_cors.cross_origin()
def transect_overview() -> str:
    """return transect overview in geojson format"""
    df = datasets.overview()
    fc = []
    for index, row in df.iterrows():
        fc.append(
            geojson.Feature(
                id= str(row.id),
                geometry=geojson.LineString(
                    coordinates=[
                        [row.lon_0, row.lat_0],
                        [row.lon_1, row.lat_1]
                    ]
                ),
                properties={
                    'lod': row.min_lod_pixels
                }
            )
        )
    geojson_output = geojson.FeatureCollection(fc)
    return flask.jsonify(geojson_output)

def transect_overview_kml() -> str:
    """create an overview of all transects"""
    lines = datasets.overview()
    return flask.render_template('lod.kml', lines=lines)


def transect_kml(
        id: int,
        extrude: bool,
        exaggeration: float,
        lift: float,
        move: float
) -> str:
    """create a kml for a specific transect"""
    # only available on runtime
    flask.current_app.jinja_env.filters['kmldate'] = utils.kmldate
    transect = datasets.get_transect(int(id), exaggeration, lift, move)
    return flask.render_template(
        "transect.kml",
        transect=transect,
        extrude=int(extrude)
    )


def transect_info(id: int) -> str:
    transect = datasets.get_transect_data(int(id))
    transect_df = pd.Series(data=transect).to_frame('transect')
    static_url = 'https://api.mapbox.com/styles/v1/mapbox/{style}/static/{lon},{lat},{zoom},{angle},{pitch}/{size}?access_token={token}'.format( # noqa E501
        lon=transect['rsp_lon'],
        lat=transect['rsp_lat'],
        angle=np.mod(transect['angle'] + 90, 360),
        zoom=13.25,
        pitch=60,
        style='satellite-v9',
        size="600x300",
        token='pk.eyJ1Ijoic2lnZ3lmIiwiYSI6ImNqNmFzMTN5YjEyYzYzMXMyc2JtcTdpdDQifQ.Cxyyltmdyy1K_lvPY2MTrQ' # noqa E501
    )
    return flask.render_template(
        "info.html",
        transect=transect_df,
        static_url=static_url,
        __version__=__version__,
        **transect              # just pass along all the properties
    )


def transect_placemark(id: int) -> str:
    transect = datasets.get_transect_data(int(id))
    transect_df = pd.Series(data=transect).to_frame('transect')
    transect_df['id'] = id
    return flask.render_template("placemark.html", transect=transect_df, id=id)


def timestack(id: int, format: str='') -> str:
    as_attachment = False

    if format:
        as_attachment = True

    data = datasets.get_transect_data(int(id))
    fig, ax = plots.timestack(data)
    stream = io.BytesIO()
    dpi = 72
    if format in ('pdf', 'png', 'svg'):
        dpi = 300
        fig.savefig(stream, bbox_inches='tight', dpi=dpi, format=format)
    else:
        fig.savefig(stream, bbox_inches='tight', dpi=dpi)
    plt.close(fig)
    mimetype = MIMES.get(format, 'image/png')
    headers = {}
    stream.seek(0)
    if as_attachment:
        filename = 'timestack.{}'.format(format)
        # this is the way to send a filename
        headers = {
            "Content-Disposition": "attachment;filename={}".format(filename)
        }
    response = flask.Response(
        stream,
        mimetype=mimetype,
        headers=headers
    )
    return response


# new eeg
def eeg(id: int) -> str:
    """Creates and returns a JSON which represents the eeg lines for a transect"""
    data = datasets.get_transect_data(int(id))
    output = plots.eeg(data)

    response = {
        "data": output
    }
    return flask.jsonify(response)



def indicators(id: int, format: str='') -> str:
    """return a plot with all the indicators"""
    as_attachment = False

    if format:
        as_attachment = True

    data = datasets.get_transect_data(int(id))
    data_mkl = datasets.get_mkl_df(int(id))
    data_bkltkltnd = datasets.get_bkltkltnd_df(int(id))
    data_mean_water = datasets.get_mean_water_df(int(id))
    data_dune_foot = datasets.get_dune_foot_df(int(id))
    data_faalkans = datasets.get_faalkans_df(int(id))
    data_nourishment_grid = datasets.get_nourishment_grid_df(int(id))

    # generate a plot
    fig, ax = plots.indicators(
        transect=data,
        mkl=data_mkl,
        bkltkltnd=data_bkltkltnd,
        mean_water=data_mean_water,
        dune_foot=data_dune_foot,
        faalkans=data_faalkans,
        nourishment=data_nourishment_grid
    )
    # create a stream to save to
    stream = io.BytesIO()

    dpi = 72
    if format in ('pdf', 'png', 'svg'):
        dpi = 300
        fig.savefig(stream, bbox_inches='tight', dpi=dpi, format=format)
    else:
        fig.savefig(stream, bbox_inches='tight', dpi=dpi)
    plt.close(fig)
    mimetype = MIMES.get(format, 'image/png')
    headers = {}
    stream.seek(0)
    if as_attachment:
        filename = 'eeg.{}'.format(format)
        # this is the way to send a filename
        headers = {
            "Content-Disposition": "attachment;filename={}".format(filename)
        }
    response = flask.Response(
        stream,
        mimetype=mimetype,
        headers=headers
    )
    return response


def styles(poly_alpha: float, outline: int, colormap: str) -> str:
    """return style information"""

    context = {}

    poly_alpha = int(float(poly_alpha) * 255)
    context['poly_alpha'] = '{:02X}'.format(poly_alpha)
    context['outline'] = int(outline)

    # Get a colormap based on the ?colormap parameter
    colormap_name = colormap
    colormap = matplotlib.cm.cmap_d.get(colormap_name, matplotlib.cm.viridis)
    colors = {}
    current_year = datetime.datetime.now().year
    # start of measurements in 1964
    N = matplotlib.colors.Normalize(1964, current_year + 1)
    for year in range(1964, current_year + 1):
        # call with float 0..1 (or int 0 .. 255)
        r, g, b, alpha = colormap(N(year))
        # r and b reversed in the google, don't forget to add alpha
        color = matplotlib.colors.rgb2hex((b, g, r)).replace('#', '')
        colors['year{0}'.format(year)] = color
    context['colors'] = colors
    return flask.render_template("styles.kml", context=context)

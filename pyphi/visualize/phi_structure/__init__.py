# visualize/phi_structure/__init__.py

import dataclasses
from collections import defaultdict
from typing import Mapping

import numpy as np
from plotly import graph_objs as go
from toolz import partition
from tqdm.auto import tqdm

from ...direction import Direction
from ...new_big_phi import PhiStructure
from . import colors, geometry, text, theme, utils

DEFAULT_THEME = theme.Theme()
GREY_THEME = theme.Grey()


def combine_figures(fig1, fig2, theme=DEFAULT_THEME, fig=None):
    if fig is None:
        fig = go.Figure()
    fig.data = fig1.data + fig2.data
    fig.update_layout(make_layout(theme=theme))
    return fig


def highlight_phi_fold(
    phi_fold,
    phi_structure,
    highlight_theme=DEFAULT_THEME,
    background_theme=GREY_THEME,
    fig=None,
    background_theme_overrides=None,
    node_indices=None,
    value_attr="phi",
    **theme_overrides,
):
    """Plot a PhiStructure with a PhiFold highlighted."""
    if background_theme_overrides is None:
        background_theme_overrides = dict()
    fig, purview_coords, mechanism_coords = plot_phi_structure(
        phi_structure,
        fig=fig,
        theme=background_theme,
        return_coords=True,
        value_attr=value_attr,
        node_indices=node_indices,
        **background_theme_overrides,
    )
    fig = plot_phi_structure(
        phi_fold,
        fig=fig,
        theme=highlight_theme,
        purview_coords=purview_coords,
        mechanism_coords=mechanism_coords,
        node_indices=node_indices,
        value_attr=value_attr,
        **theme_overrides,
    )
    return fig


def plot_phi_structure(
    phi_structure,
    fig=None,
    theme=DEFAULT_THEME,
    purview_coords=None,
    mechanism_coords=None,
    return_coords=False,
    node_indices=None,
    state=None,
    node_labels=None,
    value_attr="phi",
    **theme_overrides,
):
    """Plot a PhiStructure.

    Arguments:
        phi_structure (PhiStructure): The PhiStructure to plot.

    Keyword Arguments:
        fig (plotly.graph_objects.Figure): The figure to use. Defaults to None,
            which creates a new figure.
        theme (Theme): The visual theme to use.
        purview_coords (Coordinates): Coordinates to use when arranging
            purviews. Defaults to generating coordinates according to the theme.
        mechanism_coords (Coordinates): Coordinates to use when arranging
            mechanisms. Defaults to generating coordinates according to the theme.
        node_indices (tuple[int]): The node indices to use when arranging
            purviews. Defaults to the subsystem's node indices.
        value_attr (str): The attribute of each distinction to use as the value
            for plotting.
        **theme_overrides (Mapping): Overrides for the theme.
    """
    if not isinstance(phi_structure, PhiStructure):
        raise ValueError(
            f"phi_structure must be a PhiStructure; got {type(phi_structure)}"
        )
    if not phi_structure.distinctions:
        raise ValueError("No distinctions; cannot plot")

    if theme_overrides:
        theme = dataclasses.replace(theme, **theme_overrides)

    if fig is None:
        fig = go.Figure()
    fig.update_layout(make_layout(theme=theme))

    distinctions = phi_structure.distinctions
    subsystem = distinctions.subsystem
    if node_indices is None:
        node_indices = subsystem.node_indices
    if state is None:
        state = subsystem.state
    if node_labels is None:
        node_labels = subsystem.node_labels

    label = text.Labeler(state, node_labels)

    if purview_coords is None:
        purview_mapping = geometry.powerset_coordinates(
            node_indices,
            radius_func=geometry.SHAPES.get(theme.purview_shape, theme.purview_shape),
            purview_radius_mod=theme.purview_radius_mod,
        )
        purview_coords = geometry.Coordinates(
            purview_mapping,
            offset_subsets=distinctions.mechanisms,
            subset_offset_radius=theme.purview_offset_radius,
            direction_offset_amount=theme.direction_offset,
        )

    # Distinctions
    if theme.distinction:
        _plot_distinctions(
            fig,
            distinctions,
            purview_coords,
            label,
            theme,
            value_attr,
        )

    # Cause-effect links
    if theme.cause_effect_link:
        _plot_cause_effect_links(
            fig,
            distinctions,
            purview_coords,
            theme,
        )

    if theme.mechanism:
        if mechanism_coords is None:
            mechanism_mapping = geometry.powerset_coordinates(
                node_indices,
                max_radius=theme.mechanism_max_radius,
                z_offset=theme.mechanism_z_offset,
                z_spacing=theme.mechanism_z_spacing,
                radius_func=geometry.SHAPES.get(
                    theme.mechanism_shape, theme.mechanism_shape
                ),
            )
            mechanism_coords = geometry.Coordinates(mechanism_mapping)
        # Mechanisms
        _plot_mechanisms(fig, distinctions, mechanism_coords, label, theme)
        # Mechanism-purview links
        if theme.mechanism_purview_link:
            _plot_mechanism_purview_links(
                fig, distinctions, purview_coords, mechanism_coords, theme, value_attr
            )

    if theme.two_relation or theme.three_relation:
        # Group relations by degree
        relations = defaultdict(set)
        for relation in tqdm(
            phi_structure.relations, desc="Grouping relation faces by degree"
        ):
            for face in relation.faces:
                relations[len(face)].add((face, getattr(relation, value_attr)))

        def face_to_coords(face):
            return np.array(
                [
                    purview_coords.get(
                        relatum.purview,
                        offset_subset=relatum.mechanism,
                        direction=relatum.direction,
                    )
                    for relatum in face
                ]
            )

        # 2-relations
        if theme.two_relation and relations[2]:
            _plot_two_relation_faces(
                fig,
                face_to_coords,
                relations[2],
                label,
                theme,
            )

        # 3-relations
        if theme.three_relation and relations[3]:
            if theme.three_relation_opacity_range is None:
                _plot_three_relation_faces(
                    fig, face_to_coords, relations[3], label, theme
                )
            else:
                _plot_three_relation_faces_with_opacity(
                    fig, face_to_coords, relations[3], label, theme
                )

    if return_coords:
        return fig, purview_coords, mechanism_coords
    return fig


def make_layout(width=900, aspect=1.62, eye=None, theme=DEFAULT_THEME):
    if eye is not None:
        eye = dict(zip("xyz", geometry.spherical_to_cartesian(eye), strict=True))
    height = width / aspect
    return dict(
        scene={
            name: dict(
                showbackground=False,
                showgrid=False,
                showticklabels=False,
                showspikes=False,
                title="",
            )
            for name in ["xaxis", "yaxis", "zaxis"]
        },
        scene_camera_eye=eye,
        autosize=True,
        showlegend=True,
        hovermode="x",
        hoverlabel_font=dict(family=theme.fontfamily, size=int(0.75 * theme.fontsize)),
        title="",
        width=width,
        height=height,
        paper_bgcolor="rgba(0, 0, 0, 0)",
        plot_bgcolor="rgba(0, 0, 0, 0)",
    )


def scatter_from_coords(coords, theme=DEFAULT_THEME, **kwargs):
    """Return a Scatter3d given labels and coordinates."""
    x, y, z = np.stack(coords).transpose()
    defaults = dict(
        mode="text",
        textposition="middle center",
        textfont=dict(family=theme.fontfamily, size=theme.fontsize),
        hoverinfo="text",
        showlegend=True,
    )
    return go.Scatter3d(
        x=x,
        y=y,
        z=z,
        **{**defaults, **kwargs},
    )


def lines_from_coords(coords, **kwargs):
    """Return a Scatter3d line plot given labels and coordinates.

    Assumes ``coords`` has shape (<num_lines>, 2, 3), where the second dimension
    indexes start and end, and the third dimension indexes x, y, and z
    coordinates.
    """
    x, y, z = [
        _individual_lines_from_one_dimensional_coords(coords[:, :, i]) for i in range(3)
    ]
    defaults = dict(
        mode="lines",
        hoverinfo="text",
        showlegend=True,
    )
    return go.Scatter3d(
        x=x,
        y=y,
        z=z,
        **{**defaults, **kwargs},
    )


def _individual_lines_from_one_dimensional_coords(one_dimensional_coords):
    """Return a single coordinate list with gaps to plot unconnected lines with
    Scatter3d.

    ``one_dimensional_coords`` assumed to have shape (<num_lines>, 2), where the
    second dimension indexes start and end points.
    """
    x = np.empty(len(one_dimensional_coords) * 3)
    x[0::3] = one_dimensional_coords[:, 0]
    x[1::3] = one_dimensional_coords[:, 1]
    x[2::3] = np.nan
    return x


def _plot_distinctions(
    fig,
    distinctions,
    purview_coords,
    label,
    theme,
    value_attr,
):
    values = [getattr(distinction, value_attr) for distinction in distinctions]
    marker_size = utils.rescale(values, theme.point_size_range)
    # TODO convert to flat CES and plot as one trace
    for direction, color in zip(
        Direction.both(), [theme.cause_color, theme.effect_color], strict=True
    ):
        coords = [
            purview_coords.get(
                distinction.purview(direction),
                offset_subset=distinction.mechanism,
                direction=direction,
            )
            for distinction in distinctions
        ]
        labels = [
            # TODO currently labeling current state only; decide if that's right
            # and and refactor
            label.nodes(distinction.purview(direction))
            for distinction in distinctions
        ]
        hovertext = [
            label.hover(distinction.mice(direction)) for distinction in distinctions
        ]
        fig.add_trace(
            scatter_from_coords(
                coords,
                theme=theme,
                name=f"{direction} distinctions" + theme.legendgroup_postfix,
                text=labels,
                textfont_color=color,
                hovertext=hovertext,
                hoverlabel_bgcolor=color,
                opacity=theme.distinction_opacity,
                mode=theme.distinction_mode,
                marker=dict(
                    symbol="circle",
                    color=values,
                    colorscale=theme.distinction_colorscale,
                    size=marker_size,
                    # coloraxis="coloraxis",
                    # cmin=theme.distinction_color_range[0],
                    # cmax=theme.distinction_color_range[0],
                ),
            )
        )


def _plot_cause_effect_links(
    fig,
    distinctions,
    purview_coords,
    theme,
):
    # TODO make this scaling consistent with 2-relation phi?
    name = "Cause-effect links" + theme.legendgroup_postfix
    widths = utils.rescale(distinctions.phis, theme.line_width_range)
    showlegend = True
    link_coords = []
    for distinction, width in zip(distinctions, widths, strict=True):
        coords = np.stack(
            [
                purview_coords.get(
                    distinction.purview(direction),
                    offset_subset=distinction.mechanism,
                    direction=direction,
                )
                for direction in Direction.both()
            ]
        )
        link_coords.append(coords)
        x, y, z = coords.transpose()
        fig.add_trace(
            go.Scatter3d(
                x=x,
                y=y,
                z=z,
                showlegend=showlegend,
                legendgroup=name + theme.legendgroup_postfix,
                name=name,
                mode="lines",
                line_color=theme.cause_effect_link_color,
                opacity=theme.cause_effect_link_opacity,
                line_width=width,
                hoverinfo="skip",
            )
        )
        showlegend = False
    return link_coords


def _plot_mechanisms(fig, distinctions, mechanism_coords, label, theme):
    name = "Mechanisms" + theme.legendgroup_postfix
    labels = []
    coords = []
    for mechanism in distinctions.mechanisms:
        labels.append(label.nodes(mechanism))
        coords.append(mechanism_coords.get(mechanism))
    fig.add_trace(
        scatter_from_coords(
            coords,
            theme=theme,
            text=labels,
            legendgroup=name + theme.legendgroup_postfix,
            name=name,
            hoverinfo="skip",
        )
    )


def _plot_mechanism_purview_links(
    fig,
    distinctions,
    purview_coords,
    mechanism_coords,
    theme,
    value_attr,
):
    name = "Mechanism-purview links" + theme.legendgroup_postfix
    # TODO make this scaling consistent with 2-relation phi?
    values = [getattr(distinction, value_attr) for distinction in distinctions]
    widths = utils.rescale(values, theme.line_width_range)
    showlegend = True
    for distinction, width in zip(distinctions, widths, strict=True):
        coords = np.stack(
            [
                purview_coords.get(
                    distinction.purview(Direction.CAUSE),
                    offset_subset=distinction.mechanism,
                    direction=Direction.CAUSE,
                ),
                mechanism_coords.get(distinction.mechanism),
                purview_coords.get(
                    distinction.purview(Direction.EFFECT),
                    offset_subset=distinction.mechanism,
                    direction=Direction.EFFECT,
                ),
            ]
        )
        x, y, z = coords.transpose()
        fig.add_trace(
            go.Scatter3d(
                x=x,
                y=y,
                z=z,
                showlegend=showlegend,
                legendgroup=name + theme.legendgroup_postfix,
                name=name,
                mode="lines",
                line_color=theme.mechanism_purview_link_color,
                opacity=theme.mechanism_purview_link_opacity,
                line_width=width,
                hoverinfo="skip",
            )
        )
        showlegend = False


def _plot_two_relation_faces(fig, face_to_coords, relation_faces, label, theme):
    name = "2-relations" + theme.legendgroup_postfix
    faces, values = list(zip(*relation_faces, strict=True))
    values = np.array(values)

    showlegend = True
    if len(faces) >= theme.two_relation_detail_threshold:
        coords = np.array([face_to_coords(face) for face in faces])
        # Single trace for all faces
        fig.add_trace(
            lines_from_coords(
                coords,
                showlegend=showlegend,
                legendgroup=name + theme.legendgroup_postfix,
                name=name,
                mode="lines",
                line=go.scatter3d.Line(
                    width=theme.two_relation_line_width,
                    color=(
                        values
                        if not theme.two_relation_color
                        else theme.two_relation_color
                    ),
                    # colorscale=theme.two_relation_colorscale,
                    coloraxis="coloraxis2",
                    # showscale=theme.two_relation_showscale,
                    # reversescale=theme.two_relation_reversescale,
                    # colorbar=dict(
                    #     title=dict(text="2-face φ_r", font_size=theme.fontsize),
                    #     x=-0.1,
                    #     len=1.0,
                    # ),
                ),
                opacity=theme.two_relation_opacity,
                hoverinfo="text",
                # hovertext=label.relation(faces),
                # hoverlabel_font_color=theme.two_relation_hoverlabel_font_color,
            )
        )
    else:
        line_colors = _two_relation_line_colors(theme, faces, values)
        widths = utils.rescale(values, theme.line_width_range)
        # Individual trace for each face
        for face, width, line_color in zip(
            faces,
            widths,
            line_colors,
            strict=True,
        ):
            x, y, z = face_to_coords(face).transpose()
            fig.add_trace(
                go.Scatter3d(
                    x=x,
                    y=y,
                    z=z,
                    showlegend=showlegend,
                    legendgroup=name + theme.legendgroup_postfix,
                    name=name,
                    mode="lines",
                    line_color=line_color,
                    opacity=theme.two_relation_opacity,
                    line_width=width,
                    hoverinfo="text",
                    # hovertext=label.relation(faces),
                    # hoverlabel_font_color=theme.two_relation_hoverlabel_font_color,
                )
            )
            # Only show the first trace in the legend
            showlegend = False


def _two_relation_line_colors(theme, faces, values):
    if isinstance(theme.two_relation_colorscale, Mapping):
        # Map to relation type
        line_colors = map(
            theme.two_relation_colorscale.get, map(colors.two_relation_face_type, faces)
        )
    elif theme.two_relation_colorscale in colors.TWO_RELATION_COLORSCHEMES:
        # Library function
        line_colors = map(
            colors.TWO_RELATION_COLORSCHEMES[theme.two_relation_colorscale], faces
        )
    elif isinstance(theme.two_relation_colorscale, str):
        # Plotly colorscale
        scaled_values = utils.rescale(values, (0, 1))

        def colorize(value):
            return colors.get_color(theme.two_relation_colorscale, value)

        line_colors = map(colorize, scaled_values)
    else:
        # Callable
        line_colors = map(theme.two_relation_colorscale, faces)
    return list(line_colors)


def _plot_three_relation_faces(fig, face_to_coords, relation_faces, label, theme):
    name = "3-relations" + theme.legendgroup_postfix
    # Build vertices:
    # Stack the [relation, relata] axes together and tranpose to put the 3D axis
    # first to get lists of x, y, z coordinates
    x, y, z = np.vstack(
        list(map(face_to_coords, [face for face, _ in relation_faces]))
    ).transpose()
    # Build triangles:
    # The vertices are stacked triples, so we want each
    # (i, j, k) = [0, 1, 2], [3, 4, 5], ...
    relata_indices = np.arange(len(relation_faces) * 3, step=3)
    i, j, k = np.tile(relata_indices, (3, 1)) + np.arange(3).reshape(3, 1)
    values = np.array(list(value for _, value in relation_faces))
    intensities = utils.rescale(values, theme.three_relation_intensity_range)
    # hovertext = list(map(label.relation, relation_faces))
    fig.add_trace(
        go.Mesh3d(
            x=x,
            y=y,
            z=z,
            i=i,
            j=j,
            k=k,
            showlegend=theme.three_relation_showlegend,
            legendgroup=name + theme.legendgroup_postfix,
            name=name,
            intensity=intensities,
            intensitymode="cell",
            colorscale=theme.three_relation_colorscale,
            showscale=theme.three_relation_showscale,
            reversescale=theme.two_relation_reversescale,
            colorbar=dict(
                title=dict(text="3-face φ_r", font_size=theme.fontsize),
                x=0.0,
                len=1.0,
            ),
            opacity=theme.three_relation_opacity,
            lighting=theme.lighting,
            hoverinfo="text",
            # hovertext=hovertext,
        )
    )


def _plot_three_relation_faces_with_opacity(
    fig, face_to_coords, relation_faces, label, theme
):
    name = "3-relations" + theme.legendgroup_postfix
    # Build vertices:
    # Stack the [relation, relata] axes together and tranpose to put the 3D axis
    # first to get lists of x, y, z coordinates
    x, y, z = np.vstack(
        list(map(face_to_coords, [face for face, _ in relation_faces]))
    ).transpose()
    values = np.array(list(value for _, value in relation_faces))
    intensities = utils.rescale(values, theme.three_relation_intensity_range)
    opacities = utils.rescale(values, theme.three_relation_opacity_range)
    # hovertexts = list(map(label.relation, relation_faces))
    showlegend = theme.three_relation_showlegend
    showscale = theme.three_relation_showscale
    for _x, _y, _z, intensity, opacity in zip(
        partition(3, x),
        partition(3, y),
        partition(3, z),
        intensities,
        opacities,
        # hovertexts,
        strict=True,
    ):
        fig.add_trace(
            go.Mesh3d(
                x=_x,
                y=_y,
                z=_z,
                i=[0],
                j=[1],
                k=[2],
                showlegend=showlegend,
                legendgroup=name + theme.legendgroup_postfix,
                name=name,
                intensity=[intensity],
                intensitymode="cell",
                colorscale=theme.three_relation_colorscale,
                showscale=showscale,
                colorbar=dict(
                    title=dict(text="φ", font_size=theme.fontsize),
                    x=0.0,
                    len=1.0,
                ),
                opacity=opacity,
                hoverinfo="text",
                # hovertext=hovertext,
                lighting=theme.lighting,
            )
        )
        showlegend = False
        showscale = False

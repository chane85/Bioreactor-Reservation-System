import os
import streamlit.components.v1 as components

_component_func = components.declare_component(
    "gantt_chart",
    path=os.path.join(os.path.dirname(os.path.abspath(__file__)), "frontend"),
)


def gantt_chart(bookings, reactors, highlight_date=None, height_per_row=28, key=None):
    """
    Drag-enabled Gantt component backed by vis.js Timeline.

    Parameters
    ----------
    bookings : list[dict]
        booking_id, reactor_id, start (YYYY-MM-DD), end (YYYY-MM-DD),
        project, stage, user, color (hex), font_color (hex)
    reactors : list[dict]
        Ordered list of {id: reactor_id, label: display_string}
    highlight_date : str | None
        "YYYY-MM-DD" blue guide line, or None.
    height_per_row : int
        Pixel height per reactor row.
    key : str | None
        Streamlit widget key.

    Returns
    -------
    dict | None
        {action, booking_id, new_reactor_id, new_start, new_end, ts} on drag-end.
        None on initial render or when no new drag has occurred.
    """
    return _component_func(
        bookings=bookings,
        reactors=reactors,
        highlight_date=highlight_date,
        height_per_row=height_per_row,
        key=key,
        default=None,
    )

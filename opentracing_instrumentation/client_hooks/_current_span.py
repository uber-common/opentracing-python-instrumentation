
from .. import get_current_span

current_span_func = get_current_span


def set_current_span_func(span_extractor_func):
    """
    A convenience method to override the default method
      to extract parent span.
    It has to be called before install_patches
     :parent span_extractor_func : a function that returns parent span
    """
    global current_span_func
    current_span_func = span_extractor_func

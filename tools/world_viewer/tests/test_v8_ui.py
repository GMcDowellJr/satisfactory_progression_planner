import world_viewer.vtk_view as vv


def test_wrapped_overlay_is_bounded():
    text=' '.join(['control']*80)
    wrapped=vv._wrapped(text, width=40)
    assert len(wrapped.splitlines()) > 1
    assert max(len(x) for x in wrapped.splitlines()) <= 40


def test_viewer_source_uses_exclusive_letter_size_hotkeys_and_tiny_slider_span():
    src=open(vv.__file__, encoding='utf-8').read()
    assert 'key in {"s", "m", "l", "v"}' in src
    assert 'visible_sizes.clear(); visible_sizes.add(name)' in src
    assert 'Z-up locked' not in src
    assert 'SetValue(0.958, y)' in src
    assert 'SetValue(0.987, y)' in src
    assert 'SetSliderWidth(0.008)' in src


def test_class_specific_coverage_layer_name():
    assert vv._coverage_layer_for_sizes({'small'}) == 'coverage_small_labels'
    assert vv._coverage_layer_for_sizes({'medium'}) == 'coverage_medium_labels'
    assert vv._coverage_layer_for_sizes({'large'}) == 'coverage_large_labels'
    assert vv._coverage_layer_for_sizes({'very_large'}) == 'coverage_very_large_labels'
    assert vv._coverage_layer_for_sizes({'small','medium'}) == 'coverage_labels'

"""Code removed on 2026-11-11 (unused by the experiment; kept for reference)."""

# ---- from code/pleasure_pipeline.py (function)
def select_symmetric_intensity_range(
    threshold,
    maximum_intensity,
    minimum_allowed,
    adjustment_step,
):
    values = (threshold, maximum_intensity, minimum_allowed, adjustment_step)
    if not all(math.isfinite(value) for value in values):
        raise ValueError("Threshold and intensity settings must be finite numbers.")
    if adjustment_step <= 0:
        raise ValueError("adjustment_step must be positive.")
    if maximum_intensity <= minimum_allowed:
        raise ValueError("maximum_intensity must exceed minimum_allowed.")

    adjusted_threshold = threshold
    if maximum_intensity - adjusted_threshold < adjustment_step:
        adjusted_threshold = maximum_intensity - adjustment_step

    minimum_intensity = adjusted_threshold - adjustment_step
    selected_maximum = adjusted_threshold + adjustment_step
    if minimum_intensity < minimum_allowed:
        raise ValueError(
            "The pleasure threshold does not leave room "
            "for a symmetric final intensity range above the configured "
            "minimum intensity."
        )
    if selected_maximum > maximum_intensity:
        selected_maximum = maximum_intensity
        minimum_intensity = 2 * adjusted_threshold - selected_maximum
    if not minimum_intensity < adjusted_threshold < selected_maximum:
        raise ValueError(
            "Could not create a symmetric intensity range around the "
            "pleasure threshold."
        )

    return minimum_intensity, adjusted_threshold, selected_maximum

# ---- from code/pleasure_pipeline.py (function)
def select_three_intensities(
    threshold,
    uncertainty,
    minimum_intensity,
    safe_ceiling,
    intensity_step,
):
    values = (
        threshold,
        uncertainty,
        minimum_intensity,
        safe_ceiling,
        intensity_step,
    )
    if not all(math.isfinite(value) for value in values):
        raise ValueError("Threshold and intensity settings must be finite numbers.")
    if uncertainty < 0 or intensity_step <= 0:
        raise ValueError("Uncertainty must be nonnegative and intensity_step positive.")
    if safe_ceiling <= minimum_intensity:
        raise ValueError("safe_ceiling must be above minimum_intensity.")

    range_width = safe_ceiling - minimum_intensity
    step_count = math.floor(range_width / intensity_step)
    if step_count > 10000:
        raise ValueError("intensity_step creates an impractically fine test grid.")
    grid = [
        round(minimum_intensity + index * intensity_step, 10)
        for index in range(step_count + 1)
    ]
    if not math.isclose(grid[-1], safe_ceiling, abs_tol=1e-9):
        grid.append(round(safe_ceiling, 10))

    if len(grid) < 3:
        raise ValueError(
            "The safe intensity range contains fewer than three distinct "
            "intensities; widen the safe range or reduce intensity_step."
        )

    targets = [
        min(safe_ceiling, max(minimum_intensity, threshold - 2 * uncertainty)),
        min(safe_ceiling, max(minimum_intensity, threshold)),
        min(safe_ceiling, max(minimum_intensity, threshold + 2 * uncertainty)),
    ]
    target_costs = [
        [(level - target) ** 2 for level in grid]
        for target in targets
    ]

    best_prefix_cost = [target_costs[0][0]]
    best_prefix_index = [0]
    for index in range(1, len(grid)):
        if target_costs[0][index] < best_prefix_cost[-1]:
            best_prefix_cost.append(target_costs[0][index])
            best_prefix_index.append(index)
        else:
            best_prefix_cost.append(best_prefix_cost[-1])
            best_prefix_index.append(best_prefix_index[-1])

    pair_costs = [math.inf] * len(grid)
    pair_first_indices = [None] * len(grid)
    for second_index in range(1, len(grid)):
        first_index = best_prefix_index[second_index - 1]
        pair_costs[second_index] = (
            best_prefix_cost[second_index - 1]
            + target_costs[1][second_index]
        )
        pair_first_indices[second_index] = first_index

    best_total = math.inf
    best_levels = None
    best_second_index = None
    best_pair_cost = math.inf
    best_pair_index = None
    for third_index in range(2, len(grid)):
        candidate_second_index = third_index - 1
        if pair_costs[candidate_second_index] < best_pair_cost:
            best_pair_cost = pair_costs[candidate_second_index]
            best_pair_index = candidate_second_index

        total_cost = best_pair_cost + target_costs[2][third_index]
        if total_cost < best_total:
            best_total = total_cost
            best_second_index = best_pair_index
            best_levels = (
                grid[pair_first_indices[best_pair_index]],
                grid[best_pair_index],
                grid[third_index],
            )

    if best_levels is None or best_second_index is None:
        raise ValueError("Could not select three distinct safe intensity levels.")
    return best_levels

# ---- from tests/test_pleasure_pipeline.py (tests)
    def test_intensity_selection_keeps_three_levels_when_plus_two_sd_is_capped(self):
        levels = select_three_intensities(
            threshold=0.75,
            uncertainty=0.2,
            minimum_intensity=0.1,
            safe_ceiling=0.8,
            intensity_step=0.05,
        )

        self.assertEqual(len(set(levels)), 3)
        self.assertLessEqual(max(levels), 0.8)

# ---- from tests/test_pleasure_pipeline.py (tests)
    def test_three_levels_are_distinct_and_below_safe_ceiling(self):
        levels = select_three_intensities(
            threshold=0.72,
            uncertainty=0.12,
            minimum_intensity=0.1,
            safe_ceiling=0.8,
            intensity_step=0.05,
        )

        self.assertEqual(len(set(levels)), 3)
        self.assertEqual(tuple(sorted(levels)), levels)
        self.assertLessEqual(max(levels), 0.8)
        self.assertTrue(all(0.1 <= level for level in levels))

# ---- from tests/test_pleasure_pipeline.py (tests)
    def test_symmetric_range_rejects_minimum_below_configured_limit(self):
        with self.assertRaisesRegex(ValueError, "leave room"):
            select_symmetric_intensity_range(
                threshold=0.15,
                maximum_intensity=0.65,
                minimum_allowed=0.1,
                adjustment_step=0.1,
            )

# ---- from tests/test_pleasure_pipeline.py (tests)
    def test_symmetric_range_uses_one_adjustment_step_around_threshold(self):
        minimum, threshold, maximum = select_symmetric_intensity_range(
            threshold=0.36,
            maximum_intensity=0.65,
            minimum_allowed=0.1,
            adjustment_step=0.1,
        )

        self.assertAlmostEqual(minimum, 0.26)
        self.assertAlmostEqual(threshold, 0.36)
        self.assertAlmostEqual(maximum, 0.46)

# ---- from tests/test_pleasure_pipeline.py (tests)
    def test_symmetric_range_lowers_threshold_if_max_is_too_close(self):
        minimum, adjusted_threshold, maximum = select_symmetric_intensity_range(
            threshold=0.5,
            maximum_intensity=0.55,
            minimum_allowed=0.1,
            adjustment_step=0.1,
        )

        self.assertAlmostEqual(adjusted_threshold, 0.45)
        self.assertAlmostEqual(minimum, 0.35)
        self.assertAlmostEqual(maximum, 0.55)
        self.assertAlmostEqual(
            (adjusted_threshold - minimum),
            (maximum - adjusted_threshold),
        )

# ---- from code/repeat_vibration.py (unused; ButtplugClient was never imported)
async def scan_for_devices():
    client = ButtplugClient("My Client")
    await client.connect("ws://127.0.0.1:12345")
    #Print("Scanning for devices")

    # Scan once
    await client.start_scanning()
    await asyncio.sleep(5)
    await client.stop_scanning()
    print("Devices found:", client.devices)

    return client

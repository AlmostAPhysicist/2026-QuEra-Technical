using GLMakie

# Noise levels
p1 = [0.0, 0.05, 0.25, 0.6]

# Fidelities
baseline_fid = [1.0000, 0.9820, 0.9340, 0.8080]
postselected_fid = [1.0000, 1.0000, 1.0000, 1.0000]
corrected_fid = [1.0000, 1.0000, 0.9980, 0.9800]

# Waste fraction
waste_frac = [0.0000, 0.0600, 0.2480, 0.5780]

# Average injected flips per shot
flips_0 = [1.000, 0.940, 0.752, 0.418]
flips_1 = [0.000, 0.056, 0.228, 0.522]
flips_2 = [0.000, 0.004, 0.018, 0.056]
flips_3 = [0.000, 0.000, 0.002, 0.004]

# Figure layout
fig = Figure(resolution=(900, 800))

ax_top = Axis(fig[1, 1], ylabel="Fidelity", title="Fidelities")
ax_mid = Axis(fig[2, 1], ylabel="Avg injected flips")
ax_bot = Axis(fig[3, 1], ylabel="Waste fraction", xlabel="Physical error scale p₁")

# --- Top panel: fidelities ---
lines!(ax_top, p1, baseline_fid; marker=:rect, label="Baseline")
lines!(ax_top, p1, postselected_fid; marker=:rect, label="Postselected")
lines!(ax_top, p1, corrected_fid; marker=:rect, label="Corrected")
axislegend(ax_top, position=:rb)

# --- Middle panel: injected flips ---
lines!(ax_mid, p1, flips_0; marker=:rect, label="0 flips")
lines!(ax_mid, p1, flips_1; marker=:rect, label="1 flip")
lines!(ax_mid, p1, flips_2; marker=:rect, label="2 flips")
lines!(ax_mid, p1, flips_3; marker=:rect, label="3 flips")
axislegend(ax_mid, position=:rb)

# --- Bottom panel: waste fraction ---
lines!(ax_bot, p1, waste_frac; marker=:rect, label="Waste fraction")
axislegend(ax_bot, position=:lt)

fig
save("memory_benchmark_fidelities.png", fig)
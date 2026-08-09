import React from 'react';

import Grid from '@mui/material/Grid';
import Slider from '@mui/material/Slider';
import Typography from '@mui/material/Typography';

import Checkbox from '../../Checkbox';

// FFmpeg eq/hue based color correction.
function init(initialState) {
	const state = {
		enabled: false,
		brightness: 0,
		contrast: 1,
		saturation: 1,
		hue: 0,
		...initialState,
	};

	return state;
}

function createGraph(settings) {
	settings = init(settings);

	if (!settings.enabled) {
		return '';
	}

	const eq = `eq=brightness=${Number(settings.brightness).toFixed(2)}:contrast=${Number(settings.contrast).toFixed(
		2,
	)}:saturation=${Number(settings.saturation).toFixed(2)}`;
	const hue = Number(settings.hue) !== 0 ? `hue=h=${Number(settings.hue).toFixed(1)}` : '';

	return hue.length ? `${eq},${hue}` : eq;
}

function ValueSlider({ label, value, min, max, step, onChange }) {
	return (
		<Grid item xs={12} md={6}>
			<Typography variant="body2">{label}</Typography>
			<Slider
				value={Number(value)}
				min={min}
				max={max}
				step={step}
				valueLabelDisplay="auto"
				onChange={(_, newValue) => onChange(newValue)}
			/>
		</Grid>
	);
}

ValueSlider.defaultProps = {
	label: '',
	value: 0,
	min: 0,
	max: 1,
	step: 0.01,
	onChange: () => {},
};

function Filter(props) {
	const settings = init(props.settings);

	const handleChange = (newSettings) => {
		let automatic = false;
		if (!newSettings) {
			newSettings = settings;
			automatic = true;
		}
		props.onChange(newSettings, createGraph(newSettings), automatic);
	};

	const update = (what) => (value) => {
		const newSettings = {
			...settings,
			[what]: value,
		};
		handleChange(newSettings);
	};

	React.useEffect(() => {
		handleChange(null);
		// eslint-disable-next-line react-hooks/exhaustive-deps
	}, []);

	return (
		<React.Fragment>
			<Grid item xs={12}>
				<Checkbox label="Color correction" checked={settings.enabled} onChange={() => update('enabled')(!settings.enabled)} />
			</Grid>
			{settings.enabled && (
				<React.Fragment>
					<ValueSlider label="Brightness" value={settings.brightness} min={-1} max={1} step={0.01} onChange={update('brightness')} />
					<ValueSlider label="Contrast" value={settings.contrast} min={0} max={2} step={0.01} onChange={update('contrast')} />
					<ValueSlider label="Saturation" value={settings.saturation} min={0} max={3} step={0.01} onChange={update('saturation')} />
					<ValueSlider label="Hue" value={settings.hue} min={-180} max={180} step={1} onChange={update('hue')} />
				</React.Fragment>
			)}
		</React.Fragment>
	);
}

Filter.defaultProps = {
	settings: {},
	onChange: function (settings, graph, automatic) {},
};

const filter = 'color';
const name = 'Color correction';
const type = 'video';
const hwaccel = false;

function summarize(settings) {
	return `${name}`;
}

function defaults() {
	const settings = init({});
	return {
		settings: settings,
		graph: createGraph(settings),
	};
}

export { name, filter, type, hwaccel, summarize, defaults, createGraph, Filter as component };

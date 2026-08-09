import React from 'react';

import Grid from '@mui/material/Grid';
import Slider from '@mui/material/Slider';
import Typography from '@mui/material/Typography';
import MenuItem from '@mui/material/MenuItem';

import Checkbox from '../../Checkbox';
import Select from '../../Select';
import UploadButton from '../../UploadButton';

const LOGO_MARKER = '__onside_logo__';

function init(initialState) {
	const state = {
		enabled: false,
		logoPath: '',
		logoUrl: '',
		position: 'top-right',
		size: 0.18,
		opacity: 0.9,
		...initialState,
	};

	return state;
}


function createGraph(settings) {
	settings = init(settings);
	return settings.enabled && settings.logoUrl ? LOGO_MARKER : '';
}

function Position(props) {
	return (
		<Select label="Logo position" value={props.value} onChange={props.onChange}>
			<MenuItem value="top-left">
				Top left
			</MenuItem>
			<MenuItem value="top-right">
				Top right
			</MenuItem>
			<MenuItem value="bottom-left">
				Bottom left
			</MenuItem>
			<MenuItem value="bottom-right">
				Bottom right
			</MenuItem>
		</Select>
	);
}

Position.defaultProps = {
	value: 'top-right',
	onChange: () => {},
};

function Preview({ url, position, size, opacity }) {
	if (!url) {
		return null;
	}

	const positionStyle = {
		top: position.startsWith('top') ? '8%' : 'auto',
		bottom: position.startsWith('bottom') ? '8%' : 'auto',
		left: position.endsWith('left') ? '8%' : 'auto',
		right: position.endsWith('right') ? '8%' : 'auto',
		width: `${Math.round(Number(size) * 100)}%`,
		opacity: Number(opacity),
	};

	return (
		<div
			style={{
				position: 'relative',
				width: '100%',
				aspectRatio: '16 / 9',
				background:
					'linear-gradient(135deg, #172033 0%, #27324a 50%, #111827 100%)',
				borderRadius: 8,
				overflow: 'hidden',
			}}
		>
			<div
				style={{
					position: 'absolute',
					inset: 0,
					display: 'flex',
					alignItems: 'center',
					justifyContent: 'center',
					color: 'rgba(255,255,255,.55)',
					fontSize: 18,
				}}
			>
				Onside Restreamer
			</div>
			<img
				src={url}
				alt="Logo preview"
				style={{
					position: 'absolute',
					height: 'auto',
					...positionStyle,
				}}
			/>
		</div>
	);
}

function Filter(props) {
	const settings = init(props.settings);
	const [$previewUrl, setPreviewUrl] = React.useState(settings.logoUrl || '');
	const [$uploading, setUploading] = React.useState(false);
	const [$error, setError] = React.useState('');

	const coreAddress = (props.coreAddress || '').replace(/\/+$/, '');

	const handleChange = (newSettings) => {
		let automatic = false;
		if (!newSettings) {
			newSettings = settings;
			automatic = true;
		}
		props.onChange(newSettings, createGraph(newSettings), automatic);
	};

	const update = (what) => (eventOrValue) => {
		const value =
			typeof eventOrValue === 'number' || typeof eventOrValue === 'string'
				? eventOrValue
				: eventOrValue.target.value;

		const newSettings = {
			...settings,
			[what]: value,
		};

		handleChange(newSettings);
	};

	const handleUpload = async (data, extension, mimetype) => {
		setError('');
		setUploading(true);

		try {
			const path = await props.onStore(`onside-logo.${extension}`, data);
			if (!path || typeof path !== 'string') {
				throw new Error('Logo upload failed');
			}

			const normalizedPath = path.startsWith('/') ? path : `/${path}`;
			const url = `${coreAddress}${normalizedPath}`;
			const previewUrl = URL.createObjectURL(new Blob([data], { type: mimetype }));

			if ($previewUrl && $previewUrl.startsWith('blob:')) {
				URL.revokeObjectURL($previewUrl);
			}

			setPreviewUrl(previewUrl);

			handleChange({
				...settings,
				enabled: true,
				logoPath: path,
				logoUrl: url,
			});
		} catch (err) {
			setError(err?.message || 'Logo upload failed');
		} finally {
			setUploading(false);
		}
	};

	React.useEffect(() => {
		if (settings.logoUrl && !$previewUrl) {
			setPreviewUrl(settings.logoUrl);
		}
		// eslint-disable-next-line react-hooks/exhaustive-deps
	}, [settings.logoUrl]);

	React.useEffect(() => {
		handleChange(null);
		// eslint-disable-next-line react-hooks/exhaustive-deps
	}, []);

	React.useEffect(() => {
		return () => {
			if ($previewUrl && $previewUrl.startsWith('blob:')) {
				URL.revokeObjectURL($previewUrl);
			}
		};
	}, [$previewUrl]);

	return (
		<React.Fragment>
			<Grid item xs={12}>
				<Checkbox
					label="Logo overlay"
					checked={settings.enabled}
					disabled={!settings.logoUrl}
					onChange={() => handleChange({ ...settings, enabled: !settings.enabled })}
				/>
			</Grid>
			<Grid item xs={12}>
				<UploadButton
					label={uploadingLabel($uploading)}
					acceptTypes={[
						{ mimetype: 'image/png', extension: 'png', maxSize: 5 * 1024 * 1024 },
						{ mimetype: 'image/jpeg', extension: 'jpg', maxSize: 5 * 1024 * 1024 },
						{ mimetype: 'image/webp', extension: 'webp', maxSize: 5 * 1024 * 1024 },
					]}
					disabled={$uploading}
					onStart={() => {
						setError('');
						setUploading(true);
					}}
					onError={(err) => {
						setUploading(false);
						setError(err.type || 'Logo upload failed');
					}}
					onUpload={handleUpload}
				/>
			</Grid>
			{settings.logoUrl && (
				<React.Fragment>
					<Grid item xs={12} md={6}>
						<Position value={settings.position} onChange={update('position')} />
					</Grid>
					<Grid item xs={12} md={6}>
						<Typography variant="body2">
							Logo size
						</Typography>
						<Slider
							value={Number(settings.size)}
							min={0.05}
							max={0.5}
							step={0.01}
							valueLabelDisplay="auto"
							valueLabelFormat={(value) => `${Math.round(value * 100)}%`}
							onChange={(_, value) => update('size')(value)}
						/>
					</Grid>
					<Grid item xs={12}>
						<Typography variant="body2">
							Logo opacity
						</Typography>
						<Slider
							value={Number(settings.opacity)}
							min={0.1}
							max={1}
							step={0.01}
							valueLabelDisplay="auto"
							valueLabelFormat={(value) => `${Math.round(value * 100)}%`}
							onChange={(_, value) => update('opacity')(value)}
						/>
					</Grid>
					<Grid item xs={12}>
						<Preview url={$previewUrl || settings.logoUrl} position={settings.position} size={settings.size} opacity={settings.opacity} />
					</Grid>
				</React.Fragment>
			)}
			{$error && (
				<Grid item xs={12}>
					<Typography color="error" variant="caption">
						{$error}
					</Typography>
				</Grid>
			)}
		</React.Fragment>
	);
}

function uploadingLabel(uploading) {
	return uploading ? 'Uploading…' : 'Upload logo';
}

Filter.defaultProps = {
	settings: {},
	coreAddress: '',
	onStore: async () => '',
	onChange: function (settings, graph, automatic) {},
};

const filter = 'logo';
const name = 'Logo overlay';
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

export { LOGO_MARKER, name, filter, type, hwaccel, summarize, defaults, createGraph, Filter as component };

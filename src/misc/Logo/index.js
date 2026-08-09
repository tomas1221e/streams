import React from 'react';

import makeStyles from '@mui/styles/makeStyles';

import company_logo from './images/onside-ball.svg';

const useStyles = makeStyles((theme) => ({
	Logo: {
		height: 27,
	},
}));

export default function Logo(props) {
	const classes = useStyles();

	let link = '#';

	// eslint-disable-next-line no-useless-escape
	return (
		<a href={link} className={classes.Logo} target="_blank" rel="noopener noreferrer">
			<img src={company_logo} alt="Onside Restreamer" />
		</a>
	);
}

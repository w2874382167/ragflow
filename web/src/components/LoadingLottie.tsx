import React from 'react';
import { DotLottieReact } from '@lottiefiles/dotlottie-react';

const LoadingLottie = () => {
  return (
    <div style={{ width: '100%', display: 'flex', justifyContent: 'center' }}>
      <DotLottieReact
        autoplay
        loop
        src="@/assets/lottie_loading.json"
        style={{ height: '80px', width: '80px' }}
      />
    </div>
  );
};

export default LoadingLottie;

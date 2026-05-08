import React, { useState, useEffect } from 'react';

const StripeLogo = ({ color = "#0a2540" }) => (
  <svg xmlns="http://www.w3.org/2000/svg" width="60" height="25" fill={color} viewBox="0 0 60 25" aria-label="Stripe logo">
    <path fillRule="evenodd" d="M59.6444 14.2813h-8.062c.1843 1.9296 1.5983 2.5476 3.2032 2.5476 1.6352 0 2.9534-.3656 4.0453-.9506v3.3179c-1.1186.7115-2.5964 1.1068-4.5645 1.1068-4.011 0-6.8218-2.5122-6.8218-7.4783 0-4.19441 2.3837-7.52509 6.3017-7.52509 3.912 0 5.9537 3.28038 5.9537 7.49819 0 .3982-.0372 1.261-.0556 1.4835Zm-5.9241-5.62407c-1.0294 0-2.1739.72812-2.1739 2.58387h4.2573c0-1.85362-1.0721-2.58387-2.0834-2.58387ZM40.9547 20.303c-1.4411 0-2.322-.6087-2.9133-1.0417l-.0088 4.6271-4.1181.8755-.0014-19.19053h3.7543l.0864 1.01784c.6035-.52914 1.6114-1.29157 3.2256-1.29162 2.8925 0 5.6162 2.6052 5.6162 7.39971 0 5.2327-2.6948 7.6037-5.6409 7.6037Zm-.959-11.35573c-.9453 0-1.5376.34559-1.9669.81586l.0245 6.11967c.3997.433.9763.7813 1.9424.7813 1.5231 0 2.5437-1.6575 2.5437-3.8745 0-2.1544-1.037-3.84233-2.5437-3.84233Zm-11.7602-3.3739h4.1341V20.0088h-4.1341V5.57337Zm0-4.694699L32.3696 0v3.35821l-4.1341.87868V.878671ZM23.9198 10.2223v9.7861h-4.1156V5.57296h3.6867l.1317 1.21751c1.0035-1.7722 3.0722-1.41321 3.6209-1.21594v3.78524c-.5242-.16908-2.2894-.42779-3.3237.86253Zm-8.5525 4.7221c0 2.4275 2.5988 1.6719 3.1263 1.4609v3.3522c-.5492.3013-1.5437.5458-2.8901.5458-2.4441 0-4.2773-1.7999-4.2773-4.2379l.0173-13.17658 4.0206-.85464.0032 3.5395h3.1278V9.0857h-3.1278v5.8588-.0001Zm-4.9069.7026c0 2.9645-2.31051 4.6562-5.73464 4.6562-1.41958 0-2.92289-.2761-4.453935-.9347v-3.9319c1.382085.7516 3.093705 1.315 4.457755 1.315.91864 0 1.53106-.2459 1.53106-1.0069C6.26064 13.7786 0 14.5192 0 9.95995 0 7.04457 2.27622 5.2998 5.61655 5.2998c1.36404 0 2.72806.20934 4.09208.75351V9.9317c-1.25265-.67618-2.84332-1.05979-4.09588-1.05979-.86296 0-1.44753.24965-1.44753.8924.0001 1.85329 6.29518.97249 6.29518 5.88279v-.0001Z" clipRule="evenodd" />
  </svg>
);

const ChevronIcon = ({ isOpen, className = "" }) => (
  <svg 
    className={`ml-1 transition-transform duration-300 ${isOpen ? 'rotate-180' : ''} ${className}`} 
    width="16" height="16" viewBox="0 0 16 16" fill="none" xmlns="http://www.w3.org/2000/svg"
  >
    <path d="M4.67065 6L9.3 10.6" stroke="currentColor" strokeWidth="1.75" />
    <path d="M12.6707 6L8.67065 10" stroke="currentColor" strokeWidth="1.75" />
  </svg>
);

const HoverArrow = () => (
  <svg className="inline-block ml-1 opacity-0 group-hover:opacity-100 transition-all duration-200 transform translate-x-[-4px] group-hover:translate-x-0" width="10" height="8" viewBox="0 0 10 8" fill="none" xmlns="http://www.w3.org/2000/svg">
    <path fill="currentColor" d="M9.752 3.913 5.87 7.825l-.959-.951 2.27-2.287H0v-1.35h7.18L4.912.951 5.871 0z" />
  </svg>
);

const ProductLink = ({ title, description, color = "#635bff" }) => (
  <li className="group mb-4 last:mb-0">
    <a href="#" className="block">
      <div className="flex items-center text-[14px] font-semibold transition-colors" style={{ color }}>
        {title}
        <HoverArrow />
      </div>
      <div className="text-[13px] text-[#425466] mt-0.5">{description}</div>
    </a>
  </li>
);

const MegaMenu = ({ isOpen, onMouseEnter, onMouseLeave }) => {
  return (
    <div 
      className={`absolute top-[64px] left-0 right-0 flex justify-center transition-all duration-300 origin-top ${isOpen ? 'opacity-100 translate-y-0 pointer-events-auto' : 'opacity-0 -translate-y-2 pointer-events-none'}`}
      onMouseEnter={onMouseEnter}
      onMouseLeave={onMouseLeave}
    >
      <div className="w-full max-w-[1100px] bg-white rounded-xl shadow-[0_50px_100px_-20px_rgba(50,50,93,0.25),0_30px_60px_-30px_rgba(0,0,0,0.3)] overflow-hidden flex">
        {/* Main Content Area */}
        <div className="flex-1 grid grid-cols-4 gap-x-8 p-8">
          <div>
            <h3 className="text-[12px] font-bold text-[#425466] uppercase tracking-wider mb-6 border-b border-gray-100 pb-2">Payments</h3>
            <ul>
              <ProductLink title="Payments" description="Online payments" />
              <ProductLink title="Managed Payments" description="Merchant of record solution" />
              <ProductLink title="Payment links" description="No-code payments" />
              <ProductLink title="Checkout" description="Prebuilt Payment UIs" />
              <ProductLink title="Elements" description="Flexible UI components" />
              <ProductLink title="Payment methods" description="Access to 100+" />
              <ProductLink title="Terminal" description="In-person payments" />
              <ProductLink title="Radar" description="Fraud prevention" />
              <ProductLink title="Authorization Boost" description="Acceptance optimisations" />
              <ProductLink title="Link" description="Accelerated checkout" />
            </ul>
          </div>
          <div>
            <h3 className="text-[12px] font-bold text-[#425466] uppercase tracking-wider mb-6 border-b border-gray-100 pb-2">Revenue</h3>
            <ul>
              <ProductLink title="Billing" description="Recurring revenue" />
              <ProductLink title="Usage-based billing" description="Metered billing" />
              <ProductLink title="Subscriptions" description="Subscription management" />
              <ProductLink title="Invoicing" description="One-time or recurring" />
              <ProductLink title="Tax" description="Sales tax & VAT automation" />
              <ProductLink title="Revenue Recognition" description="Accounting automation" />
              <ProductLink title="Stripe Sigma" description="Custom reports" />
              <ProductLink title="Data Pipeline" description="Data sync" />
            </ul>
          </div>
          <div className="space-y-10">
            <div>
              <h3 className="text-[12px] font-bold text-[#425466] uppercase tracking-wider mb-6 border-b border-gray-100 pb-2">Money Management</h3>
              <ul>
                <ProductLink title="Global Payouts" description="Payouts to third parties" />
                <ProductLink title="Capital" description="Business financing" />
                <ProductLink title="Cryptocurrency" description="Wallet, stablecoin issuing" />
                <ProductLink title="Crypto On-ramp" description="Embeddable purchases" />
              </ul>
            </div>
            <div>
              <h3 className="text-[12px] font-bold text-[#425466] uppercase tracking-wider mb-6 border-b border-gray-100 pb-2">Platforms and marketplaces</h3>
              <ul>
                <ProductLink title="Connect" description="Payments for platforms" />
                <ProductLink title="Issuing" description="Physical and virtual cards" />
              </ul>
            </div>
          </div>
          <div className="border-l border-gray-100 pl-8">
            <h3 className="text-[12px] font-bold text-[#425466] uppercase tracking-wider mb-6 border-b border-gray-100 pb-2">More</h3>
            <ul className="mb-8">
              <ProductLink title="Product roadmap" description="See what's ahead" />
              <ProductLink title="Atlas" description="Start-up incorporation" />
              <ProductLink title="Climate" description="Carbon removal" />
              <ProductLink title="Identity" description="Online identity verification" />
              <ProductLink title="Financial Connections" description="Linked financial account data" />
            </ul>
            
            {/* Featured Card */}
            <div className="mt-8 rounded-lg overflow-hidden border border-gray-100 shadow-sm group/card cursor-pointer">
              <div className="h-32 overflow-hidden">
                <img 
                  src="https://images.stripeassets.com/fzn2n1nzq965/5cRV5XgALGMWv62qKuH0Rw/f0429f90b5731f51c44c47b187626bbd/sessions-banner-background_2x.png?w=608&fm=webp&q=90" 
                  alt="AI Infrastructure" 
                  className="w-full h-full object-cover transition-transform duration-500 group-hover/card:scale-105"
                />
              </div>
              <div className="p-4 bg-white">
                <h4 className="text-[14px] font-bold text-[#0a2540] mb-1">Building the economic infrastructure for AI</h4>
                <p className="text-[12px] text-[#425466] mb-3 leading-relaxed">See how Stripe is building the economic infrastructure for AI.</p>
                <div className="text-[13px] font-semibold text-[#635bff] flex items-center">
                  Watch on demand
                  <svg className="ml-1 w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24" strokeWidth="3">
                    <path d="M9 5l7 7-7 7" />
                  </svg>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};

const GeneratedMegaMenuFromImages = () => {
  const [activeMenu, setActiveMenu] = useState(null);
  const [scrolled, setScrolled] = useState(false);

  useEffect(() => {
    const handleScroll = () => setScrolled(window.scrollY > 20);
    window.addEventListener('scroll', handleScroll);
    return () => window.removeEventListener('scroll', handleScroll);
  }, []);

  return (
    <div className="min-h-screen bg-white font-sans text-[#0a2540] selection:bg-[#635bff]/20">
      {/* Header with Glassmorphism */}
      <header 
        className={`fixed top-0 left-0 w-full z-[100] transition-all duration-300 ${scrolled ? 'bg-white/80 backdrop-blur-md border-b border-gray-100' : 'bg-transparent'}`}
      >
        <div className="relative max-w-[1200px] mx-auto px-8 h-[64px] flex items-center justify-between">
          <div className="flex items-center">
            <StripeLogo />
            <nav className="ml-8 flex items-center space-x-1">
              <div 
                className={`px-4 py-2 text-[15px] font-medium cursor-pointer transition-colors flex items-center ${activeMenu === 'products' ? 'text-[#635bff]' : 'text-[#0a2540] hover:opacity-60'}`}
                onMouseEnter={() => setActiveMenu('products')}
                onMouseLeave={() => setActiveMenu(null)}
              >
                Products <ChevronIcon isOpen={activeMenu === 'products'} />
              </div>
              {['Solutions', 'Developers', 'Resources'].map((item) => (
                <div key={item} className="px-4 py-2 text-[15px] font-medium text-[#0a2540] hover:opacity-60 cursor-pointer flex items-center">
                  {item} <ChevronIcon isOpen={false} />
                </div>
              ))}
              <div className="px-4 py-2 text-[15px] font-medium text-[#0a2540] hover:opacity-60 cursor-pointer">
                Pricing
              </div>
            </nav>
          </div>

          <div className="flex items-center space-x-4">
            <button className="px-4 py-1.5 text-[14px] font-semibold text-[#0a2540] bg-white/50 border border-[#0a2540]/10 rounded-full hover:bg-white hover:shadow-sm transition-all">
              Sign in
            </button>
            <button className="px-4 py-1.5 text-[14px] font-semibold text-white bg-[#635bff] hover:bg-[#0a2540] rounded-full transition-all flex items-center group">
              Contact sales
              <svg className="ml-1 w-3 h-3 transform group-hover:translate-x-0.5 transition-transform" fill="none" stroke="currentColor" viewBox="0 0 24 24" strokeWidth="3">
                <path d="M9 5l7 7-7 7" />
              </svg>
            </button>
          </div>

          {/* Mega Menu - Positioned relative to the header container */}
          <MegaMenu 
            isOpen={activeMenu === 'products'} 
            onMouseEnter={() => setActiveMenu('products')}
            onMouseLeave={() => setActiveMenu(null)}
          />
        </div>
      </header>

      {/* Hero Section */}
      <main className="relative pt-32 pb-20 overflow-hidden">
        {/* Background Gradient */}
        <div className="absolute top-0 left-0 w-full h-[1000px] -z-10">
          <div className="absolute top-[-200px] right-[-100px] w-[1400px] h-[1200px] bg-gradient-to-bl from-[#ffcc00] via-[#ff3366] to-[#635bff] opacity-30 blur-[150px] transform rotate-12"></div>
          <div className="absolute top-[-100px] left-[-200px] w-[1000px] h-[1000px] bg-gradient-to-tr from-[#00ccff] to-[#635bff] opacity-20 blur-[120px]"></div>
        </div>

        <div className="max-w-[1200px] mx-auto px-8">
          <div className="max-w-[800px]">
            <div className="inline-flex items-center px-3 py-1 rounded-full bg-gray-100/50 text-[13px] font-medium text-[#425466] mb-8">
              Global GDP running on Stripe: <span className="ml-1 font-mono text-[#0a2540]">1.64289362%</span>
            </div>
            
            <h1 className="text-[72px] leading-[1.1] font-extrabold tracking-tight text-[#0a2540] mb-8">
              Financial infrastructure to <span className="text-transparent bg-clip-text bg-gradient-to-r from-[#635bff] to-[#00ccff]">grow your revenue.</span>
            </h1>
            
            <p className="text-[20px] leading-relaxed text-[#425466] mb-10 max-w-[680px]">
              Accept payments, offer financial services and implement custom revenue models – from your first transaction to your billionth.
            </p>

            <div className="flex items-center space-x-4">
              <button className="px-6 py-3 bg-[#635bff] text-white font-bold rounded-full hover:bg-[#0a2540] transition-all flex items-center group shadow-lg shadow-[#635bff]/20">
                Get started
                <svg className="ml-2 w-4 h-4 transform group-hover:translate-x-1 transition-transform" fill="none" stroke="currentColor" viewBox="0 0 24 24" strokeWidth="2.5">
                  <path d="M9 5l7 7-7 7" />
                </svg>
              </button>
              <button className="px-6 py-3 bg-white border border-gray-200 text-[#0a2540] font-bold rounded-full hover:border-[#0a2540] transition-all flex items-center space-x-2 shadow-sm">
                <svg viewBox="0 0 24 24" width="18" height="18" xmlns="http://www.w3.org/2000/svg">
                  <path d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92c-.26 1.37-1.04 2.53-2.21 3.31v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.09z" fill="#4285F4"/>
                  <path d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z" fill="#34A853"/>
                  <path d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.07H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.93l3.66-2.84z" fill="#FBBC05"/>
                  <path d="M12 5.38c1.62 0 3.06.56 4.21 1.66l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.07l3.66 2.84c.87-2.6 3.3-4.53 6.16-4.53z" fill="#EA4335"/>
                </svg>
                <span>Sign up with Google</span>
              </button>
            </div>
          </div>

          {/* Logos Section */}
          <div className="mt-32 grid grid-cols-5 md:grid-cols-10 gap-8 items-center opacity-50 grayscale hover:grayscale-0 transition-all duration-500">
            {['AI', 'BMW', 'amazon', 'N26', 'NVIDIA', 'axel springer', 'Google', 'MILES', 'shopify', 'JIMDO'].map((logo) => (
              <div key={logo} className="text-[18px] font-bold text-[#0a2540] text-center cursor-default hover:opacity-100 transition-opacity">
                {logo}
              </div>
            ))}
          </div>
        </div>
      </main>

      {/* Cookie Banner Placeholder */}
      <div className="fixed bottom-6 right-6 max-w-[380px] bg-white rounded-xl shadow-2xl border border-gray-100 p-6 z-[200] animate-in slide-in-from-bottom-4 duration-500">
        <p className="text-[13px] text-[#425466] mb-4 leading-relaxed">
          We use cookies to improve your experience and for marketing. Read our <a href="#" className="text-[#635bff] hover:underline">cookie policy</a> or <a href="#" className="text-[#635bff] hover:underline">manage cookies</a>.
        </p>
        <div className="flex space-x-3">
          <button className="flex-1 py-2 bg-[#635bff]/10 text-[#635bff] text-[13px] font-bold rounded-lg hover:bg-[#635bff]/20 transition-colors">Accept all</button>
          <button className="flex-1 py-2 bg-gray-50 text-[#425466] text-[13px] font-bold rounded-lg hover:bg-gray-100 transition-colors">Reject all</button>
        </div>
      </div>
    </div>
  );
};

export default GeneratedMegaMenuFromImages;

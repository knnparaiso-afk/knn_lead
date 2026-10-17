/* Custom low-poly, high-contrast ingredient miniatures for the mobile game. */
(function (root) {
    'use strict';
    const T = root.THREE;
    if (!T) return;
    const mat = (color, options) => new T.MeshStandardMaterial(Object.assign({ color, roughness: 0.42 }, options || {}));
    const gold = mat(0xf0b735, { metalness: 0.68, roughness: 0.25 });
    const ivory = mat(0xfff2d4, { roughness: 0.24 });
    const black = mat(0x191623, { roughness: 0.38 });
    const green = mat(0x35a95c, { roughness: 0.4 });
    const glass = new T.MeshPhysicalMaterial({ color: 0xd9fff5, roughness: 0.12, transmission: 0.42, transparent: true, opacity: 0.62 });
    const add = (g, geo, m, x, y, z, sx, sy, sz) => {
        const o = new T.Mesh(geo, m); o.position.set(x || 0, y || 0, z || 0);
        if (sx !== undefined) o.scale.set(sx, sy, sz);
        o.castShadow = true; o.receiveShadow = true; g.add(o); return o;
    };
    const ball = (g,m,x,y,z,sx,sy,sz,n) => add(g,new T.SphereGeometry(1,n||16,n||12),m,x,y,z,sx,sy,sz);
    const cyl = (g,m,rt,rb,h,x,y,z,n) => add(g,new T.CylinderGeometry(rt,rb,h,n||12),m,x,y,z);
    const tube = (g,pts,r,m) => {
        const p = new T.CatmullRomCurve3(pts.map(v=>new T.Vector3(v[0],v[1],v[2])));
        return add(g,new T.TubeGeometry(p,16,r,6,false),m,0,0,0);
    };
    const shape = (g,draw,m,z,depth) => {
        const s = new T.Shape(); draw(s);
        const geo = new T.ExtrudeGeometry(s,{depth:depth||0.035,bevelEnabled:true,bevelSegments:2,bevelSize:0.004,bevelThickness:0.004});
        return add(g,geo,m,0,0,z||0);
    };
    const star = (g,x,y,z,r,m) => add(g,new T.OctahedronGeometry(r,0),m,x,y,z);
    function vial(g, liquid, wide) {
        const profile = wide
            ? [[0,.01],[.07,.02],[.115,.07],[.12,.14],[.09,.19],[.04,.22],[.035,.27],[.05,.28],[0,.28]]
            : [[0,.01],[.068,.02],[.09,.06],[.08,.15],[.04,.19],[.034,.24],[.05,.25],[0,.25]];
        const pts = profile.map(p=>new T.Vector2(p[0],p[1]));
        add(g,new T.LatheGeometry(pts,18),glass,0,0,0);
        cyl(g,liquid,wide?.085:.065,wide?.09:.07,wide?.105:.08,0,wide?.072:.06,0,16);
        cyl(g,mat(0x98613a),.041,.036,.05,0,wide?.285:.26,0,10);
        cyl(g,gold,.05,.05,.014,0,wide?.257:.234,0,16);
    }
    function leaf(g,x,y,z,scale,m,angle) {
        const o=shape(g,s=>{s.moveTo(0,0);s.quadraticCurveTo(-.11,.08,-.08,.17);s.quadraticCurveTo(-.04,.25,0,.28);s.quadraticCurveTo(.05,.24,.09,.17);s.quadraticCurveTo(.11,.08,0,0);},m,z,.018);
        o.position.set(x,y,z); o.scale.setScalar(scale||1); o.rotation.z=angle||0; return o;
    }
    function feather(g) {
        shape(g,s=>{s.moveTo(-.005,.015);s.quadraticCurveTo(-.11,.10,-.08,.24);s.quadraticCurveTo(-.055,.36,.025,.405);s.quadraticCurveTo(.05,.28,.09,.17);s.quadraticCurveTo(.07,.06,-.005,.015);},mat(0x15192c,{metalness:.22,roughness:.26}),.05,.018);
        tube(g,[[-.01,.015,.08],[.005,.13,.09],[.02,.26,.09],[.025,.405,.09]],.005,gold);
        for(let i=0;i<7;i++){const y=.065+i*.043,w=.035+Math.sin(i/7*Math.PI)*.052;for(const s of [-1,1])tube(g,[[.005,y,.08],[s*w*.55,y+.02,.085],[s*w,y+.035,.08]],.0025,mat(i%2?0x324d77:0x242a48));}
    }
    const builders = {
        eye_of_newt(g){ball(g,ivory,0,.14,0,.14,.105,.115,20);ball(g,mat(0xd64e39),0,.14,.097,.075,.075,.03);add(g,new T.TorusGeometry(.058,.01,8,20),gold,0,.14,.122);ball(g,black,0,.14,.13,.022,.06,.018);ball(g,mat(0xffffff),-.03,.17,.148,.014,.014,.008,8);},
        green_bottle(g){vial(g,mat(0x26c36c,{emissive:0x0b7839,emissiveIntensity:.5,transparent:true,opacity:.82}),true);add(g,new T.TorusGeometry(.095,.008,6,18),gold,0,.075,0);star(g,0,.13,.105,.022,mat(0xdfff9d));},
        magic_spider(g){ball(g,black,0,.12,-.025,.08,.07,.105,12);ball(g,black,0,.105,.08,.052,.05,.05,12);for(const s of [-1,1])for(let i=0;i<4;i++){let z=.07-i*.05; tube(g,[[s*.035,.11,z],[s*.095,.19,z+.02],[s*.15,.12,z+.05],[s*.17,.035,z+.075]],.008,mat(0x3e304b));}for(const x of [-.022,.022])ball(g,mat(0xff365f,{emissive:0x99052a,emissiveIntensity:.7}),x,.12,.127,.012,.014,.01,8);},
        glowing_mushroom(g){cyl(g,mat(0xf2dfc8),.055,.075,.18,0,.105,0,12);ball(g,mat(0x247ec7,{emissive:0x1259a0,emissiveIntensity:.65}),0,.23,0,.15,.085,.14,16);cyl(g,mat(0x93e8ff,{emissive:0x42bde7,emissiveIntensity:.7}),.09,.09,.015,0,.19,0,14);for(const [x,y,z] of [[-.07,.26,.09],[.04,.29,.1],[.09,.23,.03]])ball(g,ivory,x,y,z,.017,.012,.012,8);},
        purple_elixir(g){vial(g,mat(0x9b46d5,{emissive:0x6c1ca4,emissiveIntensity:.7,transparent:true,opacity:.9}),true);add(g,new T.TorusGeometry(.083,.008,6,18),mat(0xe9bcff,{emissive:0x8e44c9,emissiveIntensity:.55}),0,.09,.02);for(const [x,y] of [[-.03,.09],[.025,.13],[.005,.16]])ball(g,mat(0xf0ceff),x,y,.078,.011,.011,.01,8);star(g,0,.19,.105,.021,gold);},
        dragon_tooth(g){shape(g,s=>{s.moveTo(-.08,.26);s.quadraticCurveTo(0,.31,.075,.26);s.quadraticCurveTo(.055,.16,.025,.09);s.quadraticCurveTo(.015,.045,0,.01);s.quadraticCurveTo(-.025,.015,-.035,.06);s.quadraticCurveTo(-.055,.14,-.08,.26);},mat(0xffefcb),.045,.06);tube(g,[[-.04,.24,.12],[-.015,.17,.12],[-.01,.1,.12],[-.018,.045,.12]],.003,mat(0xffffff));cyl(g,gold,.082,.08,.02,0,.035,0,12);},
        bat_wing(g){const membrane=mat(0x45305f,{side:T.DoubleSide}),rib=mat(0xb9a3cc);for(const s of [-1,1]){shape(g,p=>{p.moveTo(0,.12);p.quadraticCurveTo(s*.10,.25,s*.23,.22);p.quadraticCurveTo(s*.19,.17,s*.22,.12);p.quadraticCurveTo(s*.15,.15,s*.16,.065);p.quadraticCurveTo(s*.09,.10,s*.10,.015);p.quadraticCurveTo(s*.04,.06,0,.025);p.lineTo(0,.12);},membrane,.04,.022);tube(g,[[0,.1,.085],[s*.1,.17,.085],[s*.22,.22,.08]],.008,rib);tube(g,[[s*.02,.08,.09],[s*.08,.11,.09],[s*.10,.015,.085]],.004,rib);}ball(g,black,0,.12,.06,.04,.09,.035,10);},
        poison_apple(g){const red=mat(0xba1f43,{roughness:.24});ball(g,red,-.045,.12,0,.09,.105,.09);ball(g,red,.045,.12,0,.09,.105,.09);ball(g,mat(0x9c1738),0,.115,0,.12,.1,.09);ball(g,mat(0x45c751,{emissive:0x1a742b,emissiveIntensity:.45}),0,.1,.085,.09,.04,.025);cyl(g,mat(0x593719),.012,.009,.06,0,.22,0,8);leaf(g,.02,.24,.02,.45,green,-.5);ball(g,mat(0xffffff),-.05,.17,.078,.013,.009,.006,8);},
        pumpkin_spice(g){ball(g,mat(0xef7625),0,.12,0,.14,.105,.13);for(let i=0;i<8;i++){const a=i*Math.PI/4;ball(g,mat(i%2?0xffa044:0xe65c1c),Math.cos(a)*.065,.12,Math.sin(a)*.06,.055,.1,.048,12);}cyl(g,green,.025,.035,.07,0,.22,0,8).rotation.z=.1;},
        black_cat_fur(g){const fur=mat(0x19151e);ball(g,fur,0,.07,0,.105,.055,.085,12);for(let i=0;i<7;i++){const x=-.075+i*.025; tube(g,[[x,.07,0],[x-.012,.15,.02],[x+(i%2?.02:-.02),.21+(i%3)*.02,.015]],.013,fur);}add(g,new T.TorusGeometry(.055,.009,6,16),gold,0,.06,.09);ball(g,mat(0xa98dc0),0,.06,.095,.07,.018,.018,10);},
        raven_feather(g){feather(g);},
        crystal_shard(g){for(const [x,y,z,sx,sy,c] of [[-.045,.14,0,.065,.27,0xa958e8],[.045,.105,.02,.05,.20,0x57d7e6],[.105,.075,-.025,.04,.14,0xc79aff]])add(g,new T.CylinderGeometry(.008,sx,sy,5,1),mat(c,{emissive:c,emissiveIntensity:.15,metalness:.12,roughness:.2}),x,y,z).rotation.z=(x+.04)*1.8;},
        golden_key(g){add(g,new T.TorusGeometry(.075,.018,8,24),gold,0,.22,.02);add(g,new T.TorusGeometry(.042,.008,6,20),mat(0xffe5a1),0,.22,.045);ball(g,mat(0x55d5d9),0,.22,.05,.022,.022,.01,10);cyl(g,gold,.015,.018,.18,0,.09,0,10);add(g,new T.BoxGeometry(.045,.035,.025),gold,.02,.04,0);add(g,new T.TorusGeometry(.014,.006,6,12),gold,0,.12,.01);},
        moon_dust(g){vial(g,mat(0xb3d9ff,{emissive:0x617fbd,emissiveIntensity:.35,transparent:true,opacity:.8}),false);shape(g,s=>{s.moveTo(.045,.09);s.quadraticCurveTo(-.02,.12,-.02,.2);s.quadraticCurveTo(-.01,.27,.05,.28);s.quadraticCurveTo(-.015,.255,-.015,.19);s.quadraticCurveTo(-.01,.13,.045,.09);},mat(0xe5edff,{metalness:.25}),.095,.015);star(g,.04,.13,.12,.012,ivory);},
        snake_venom(g){vial(g,mat(0x8bcc32,{emissive:0x418b13,emissiveIntensity:.45,transparent:true,opacity:.85}),false);tube(g,[[-.12,.05,.07],[-.15,.13,.08],[-.1,.2,.09],[0,.2,.1],[.1,.13,.1],[.13,.19,.1],[.08,.24,.11]],.018,mat(0x46a832));ball(g,mat(0x54bb35),.08,.245,.11,.038,.025,.034,10);for(const x of [.07,.09])ball(g,mat(0xffdf51),x,.25,.14,.006,.007,.004,6);},
        vampire_fang(g){const gum=mat(0x9e3150);shape(g,s=>{s.moveTo(-.145,.11);s.quadraticCurveTo(-.15,.19,-.08,.19);s.quadraticCurveTo(0,.16,.08,.19);s.quadraticCurveTo(.15,.19,.145,.11);s.quadraticCurveTo(.10,.065,.065,.105);s.quadraticCurveTo(0,.13,-.065,.105);s.quadraticCurveTo(-.10,.065,-.145,.11);},gum,.035,.065);for(const x of [-.075,.075])shape(g,s=>{s.moveTo(x-.045,.17);s.quadraticCurveTo(x,.195,x+.045,.17);s.quadraticCurveTo(x+.03,.085,x+.012,.018);s.quadraticCurveTo(x,0,x-.012,.018);s.quadraticCurveTo(x-.03,.085,x-.045,.17);},ivory,.11,.05);},
        golden_bone(g){const m=mat(0xe5ad2b,{metalness:.68,roughness:.26});shape(g,s=>{s.moveTo(-.19,.12);s.quadraticCurveTo(-.23,.18,-.18,.23);s.quadraticCurveTo(-.13,.28,-.085,.22);s.lineTo(.085,.22);s.quadraticCurveTo(.13,.28,.18,.23);s.quadraticCurveTo(.23,.18,.19,.12);s.quadraticCurveTo(.15,.07,.09,.115);s.lineTo(-.09,.115);s.quadraticCurveTo(-.15,.07,-.19,.12);},m,.04,.055);tube(g,[[-.12,.18,.12],[0,.18,.13],[.12,.18,.12]],.003,mat(0xffe6a0));},
        stardust_vial(g){vial(g,mat(0xf6d645,{emissive:0xe5a91a,emissiveIntensity:.6,transparent:true,opacity:.86}),false);star(g,0,.09,.08,.025,ivory);star(g,-.03,.14,.08,.014,gold);star(g,.03,.18,.075,.013,ivory);},
        magic_clover(g){tube(g,[[0,.02,.02],[0,.09,.04],[.02,.16,.04]],.009,mat(0x24713f));for(const [x,y,a] of [[-.06,.18,-.7],[.06,.18,.7],[-.06,.26,.7],[.06,.26,-.7]]){const o=shape(g,s=>{s.moveTo(0,0);s.quadraticCurveTo(-.05,.09,-.025,.13);s.quadraticCurveTo(0,.16,.025,.13);s.quadraticCurveTo(.05,.09,0,0);},green,.055,.02);o.position.set(x,y,.055);o.rotation.z=a;o.scale.setScalar(.9);}},
        witch_candle(g){const wax=mat(0x68418a);cyl(g,wax,.075,.082,.19,0,.105,0,12);cyl(g,mat(0xb999d2),.075,.075,.012,0,.202,0,12);for(let i=0;i<5;i++){const a=i*Math.PI*2/5;ball(g,wax,Math.cos(a)*.065,.16,Math.sin(a)*.065,.018,.045,.018,8);}cyl(g,black,.006,.006,.03,0,.222,0,6);shape(g,s=>{s.moveTo(-.03,.22);s.quadraticCurveTo(-.05,.29,-.01,.34);s.quadraticCurveTo(0,.38,.015,.34);s.quadraticCurveTo(.05,.27,.03,.22);s.quadraticCurveTo(0,.2,-.03,.22);},mat(0xffa126,{emissive:0xf65b0c,emissiveIntensity:.8}),.02,.025);},
        magic_mushrooms(g){builders.glowing_mushroom(g);},
        spell_book(g){shape(g,s=>{s.moveTo(-.14,.02);s.lineTo(.14,.02);s.lineTo(.13,.18);s.lineTo(-.14,.18);},mat(0x5c2c16),.02,.05);cyl(g,gold,.01,.01,.16,-.13,.10,0);},
        blue_potion(g){vial(g,mat(0x2563eb,{emissive:0x1d4ed8,emissiveIntensity:.6,transparent:true,opacity:.85}),false);},
        green_potion(g){builders.green_bottle(g);},
        red_potion(g){vial(g,mat(0xdc2626,{emissive:0xb91c1c,emissiveIntensity:.6,transparent:true,opacity:.85}),false);},
        magic_crystal(g){builders.crystal_shard(g);},
        crystal_amulet(g){add(g,new T.TorusGeometry(.075,.015,8,20),gold,0,.15,0);star(g,0,.15,.02,.045,mat(0x38bdf8));},
        ancient_scroll(g){cyl(g,mat(0xfef3c7),.04,.04,.24,0,.12,0,12);add(g,new T.TorusGeometry(.045,.008,6,16),mat(0xd97706),0,.12,0);},
        mortar_pestle(g){cyl(g,mat(0x475569),.10,.07,.09,0,.06,0,14);cyl(g,mat(0x334155),.02,.02,.16,.04,.11,0,8).rotation.z=-.3;},
        ingredient_jar(g){cyl(g,glass,.08,.08,.16,0,.10,0,14);cyl(g,mat(0x92400e),.065,.065,.04,0,.19,0,12);},
        magic_pouch(g){ball(g,mat(0x78350f),0,.10,0,.09,.11,.08,12);add(g,new T.TorusGeometry(.045,.008,6,12),gold,0,.17,0);},
        magic_vial(g){builders.stardust_vial(g);},
        witch_staff(g){cyl(g,mat(0x5c2c16),.015,.018,.34,0,.17,0,8);star(g,0,.35,0,.04,mat(0xa855f7,{emissive:0x9333ea,emissiveIntensity:.8}));},
        magic_coin(g){cyl(g,gold,.09,.09,.015,0,.05,0,20).rotation.x=Math.PI/4;},
        treasure_chest(g){add(g,new T.BoxGeometry(.20,.12,.14),mat(0x78350f),0,.08,0);add(g,new T.TorusGeometry(.025,.006,6,12),gold,0,.08,.075);},
        magic_box(g){add(g,new T.BoxGeometry(.20,.10,.14),mat(0x78350f),0,.07,0);},
        wooden_lid(g){add(g,new T.BoxGeometry(.21,.04,.15),mat(0x92400e),0,.04,0);},
        mini_cauldron(g){cyl(g,black,.09,.07,.12,0,.08,0,14);add(g,new T.TorusGeometry(.095,.01,6,16),black,0,.13,0);}
    };
    root.WitchIngredientModels = { create(id) { if (!builders[id]) return null; const g=new T.Group(); builders[id](g); g.traverse(o=>{if(o.isMesh){o.castShadow=true;o.receiveShadow=true;}}); return g; } };
})(window);

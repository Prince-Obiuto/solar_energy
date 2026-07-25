export function generateEnergyData(){

    return{

        solar:{

            power:3.8,
            voltage:360,
            current:10.4

        },

        battery:{

            percentage:82,
            voltage:52.4,
            charging:true

        },

        inverter:{

            status:"Online",
            outputPower:2.7,
            gridConnected:true

        },

        loads:{

            totalPower:2.3,

            zones:[

                {

                    id:1,

                    name:"Library",

                    power:0.8,

                    breaker:true

                },

                {

                    id:2,

                    name:"Laboratory",

                    power:1.2,

                    breaker:true

                }

            ]

        }

    }

}
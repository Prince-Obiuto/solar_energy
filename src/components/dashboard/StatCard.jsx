export default function StatCard({

    title,

    value

}) {

    return (

        <div className="rounded-xl bg-white p-6 shadow">

            <p className="text-gray-500">

                {title}

            </p>

            <h1 className="mt-2 text-3xl font-bold">

                {value}

            </h1>

        </div>

    );

}